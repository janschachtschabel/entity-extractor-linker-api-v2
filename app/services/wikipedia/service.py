"""
Refactored Wikipedia service - main service class.

This is the new, modular Wikipedia service that integrates prompt data
as fallbacks and provides clean output with only the required fields.
"""

from collections.abc import Iterable
from typing import Any

from loguru import logger

from app.models.entity_processing_context import EntityProcessingContext

from .api.client import WikipediaAPIClient
from .constants import CHUNK_SIZE
from .fallbacks.strategies import WikipediaFallbackStrategies
from .models import WikiPage
from .utils.data_processor import WikipediaDataProcessor


class WikipediaService:
    """
    Optimized Wikipedia service with modular architecture.

    Features:
    - Clean output structure (label_de/label_en, url_de/url_en, extract)
    - Prompt data integration as fallbacks
    - Modular design with separate concerns
    - Efficient batch processing
    """

    def __init__(self, timeout: float = 30.0):
        """Initialize Wikipedia service with API client and data processor."""
        self.api_client = WikipediaAPIClient(timeout)
        self.data_processor = WikipediaDataProcessor()
        self.fallback_strategies = WikipediaFallbackStrategies(self.api_client)

    async def __aenter__(self) -> "WikipediaService":
        """Async context manager entry."""
        await self.api_client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Async context manager exit."""
        await self.api_client.__aexit__(exc_type, exc_val, exc_tb)

    async def process_entity_simple(self, entity_name: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Process entity with simple string input.

        Args:
            entity_name: Name of the entity to process
            metadata: Optional metadata dictionary

        Returns:
            Dictionary with Wikipedia data
        """
        from app.models.entity_processing_context import EntityProcessingContext

        # Create a simple context
        context = EntityProcessingContext(label=entity_name, type="unknown", metadata=metadata or {})

        # Process the entity
        result_context = await self.process_entity(context)

        # Return the Wikipedia data
        return result_context.wikipedia_data or {}

    async def process_entity(self, context: EntityProcessingContext, language: str = "de") -> EntityProcessingContext:
        """
        Process a single entity with Wikipedia linking and prompt data fallbacks.

        Args:
            context: Entity processing context with metadata
            language: Target language for Wikipedia data ("de" or "en")

        Returns:
            Updated context with Wikipedia data
        """
        logger.info(f"Processing entity: '{context.label}' (Type: {context.type or 'unknown'})")

        try:
            # Extract prompt data from metadata for fallback
            prompt_metadata = context.metadata or {}

            # Use fallback system to fetch Wikipedia data
            wiki_page = await self.fallback_strategies.fetch_with_fallbacks(
                context.label,
                lang=language,  # Use specified language as primary
                enable_fallbacks=True,
            )

            if wiki_page and self.fallback_strategies.is_page_complete(wiki_page):
                # Successfully found Wikipedia data
                context.wikipedia_data = self.data_processor.format_wiki_page(wiki_page)

                # Enhance with prompt data if Wikipedia data is missing
                context.wikipedia_data = self.data_processor.enhance_with_prompt_data(
                    context.wikipedia_data, prompt_metadata
                )

                logger.info(f"Successfully linked entity '{context.label}' with fallbacks")
            else:
                # All fallbacks failed - use prompt data as complete fallback
                logger.warning(f"No Wikipedia data found for entity: '{context.label}' (all fallbacks failed)")
                context.wikipedia_data = self.data_processor.create_empty_wikipedia_data(context.label, "not_found")

                # Enhance with prompt data
                context.wikipedia_data = self.data_processor.enhance_with_prompt_data(
                    context.wikipedia_data, prompt_metadata
                )

                # Update status if we have any prompt data
                if prompt_metadata.get("wiki_url_de") or prompt_metadata.get("wiki_url_en"):
                    context.wikipedia_data["status"] = "found_from_prompt"
                    logger.info(f"Used prompt data as fallback for '{context.label}'")

        except Exception as e:
            logger.error(f"Error processing entity '{context.label}': {e!s}")
            context.wikipedia_data = self.data_processor.create_empty_wikipedia_data(context.label, "error", str(e))

            # Even on error, try to use prompt data
            prompt_metadata = context.metadata or {}
            context.wikipedia_data = self.data_processor.enhance_with_prompt_data(
                context.wikipedia_data, prompt_metadata
            )
            logger.debug(
                f"[process_entity] After enhance_with_prompt_data (error) - wikipedia_data: {context.wikipedia_data}"
            )

        # Final step: Generate DBpedia URI using the best available data
        context.wikipedia_data = self.data_processor.finalize_dbpedia_uri(context.wikipedia_data)

        return context

    async def fetch_pages(
        self, titles: Iterable[str], lang: str = "de", fetch_other_lang: bool = True, try_capitalization: bool = True
    ) -> list[WikiPage]:
        """
        Fetch Wikipedia page information for the given titles with language resolution.

        Args:
            titles: Iterable of page titles to fetch
            lang: Primary language to fetch pages in ('de' or 'en')
            fetch_other_lang: Whether to also fetch data in the other language
            try_capitalization: Whether to try different capitalizations

        Returns:
            List[WikiPage]: List of WikiPage objects with the requested data
        """
        # Input validation
        if lang not in ("de", "en"):
            raise ValueError(f"Unsupported language: {lang}. Must be 'de' or 'en'")

        # Remove duplicates while preserving order
        unique_titles = list(dict.fromkeys(titles))
        if not unique_titles:
            logger.warning("No titles provided to fetch_pages")
            return []

        logger.info(f"Fetching {len(unique_titles)} unique {lang.upper()} Wikipedia pages")

        # Initialize result map with empty WikiPage objects
        results_map: dict[str, WikiPage] = {}
        for title in unique_titles:
            if not isinstance(title, str) or not title.strip():
                logger.warning("Invalid title: %r", title)
                continue
            if lang == "de":
                results_map[title] = WikiPage(title_de=title)
            else:
                results_map[title] = WikiPage(title_en=title)

        if not results_map:
            logger.warning("No valid titles to fetch")
            return []

        try:
            # Fetch primary language data
            primary_data, redirects = await self._fetch_language_data(list(results_map.keys()), lang)

            # Process primary language data
            found_titles = set()
            for original_title, wiki_page in results_map.items():
                final_title = redirects.get(original_title, original_title)
                if final_title in primary_data:
                    try:
                        self.data_processor.merge_page_data(wiki_page, primary_data[final_title], lang)
                        found_titles.add(original_title)
                    except Exception as e:
                        logger.error(f"Error merging {lang} data for '{original_title}': {e}")
                else:
                    logger.warning(f"No data found for '{original_title}' in {lang.upper()} Wikipedia")

            # Fetch other language data if requested
            if fetch_other_lang and found_titles:
                await self._fetch_other_language_data(results_map, primary_data, redirects, lang)

            logger.info(f"Wikipedia fetch summary: {len(found_titles)} found")
            return list(results_map.values())

        except Exception as e:
            logger.error("Error in fetch_pages: %s", str(e), exc_info=True)
            raise

    async def _fetch_language_data(self, titles: list[str], lang: str) -> tuple[dict[str, Any], dict[str, str]]:
        """Fetch data for a specific language."""
        # Split into chunks to respect API limits
        all_pages_data = {}
        all_redirects = {}

        for i in range(0, len(titles), CHUNK_SIZE):
            chunk = titles[i : i + CHUNK_SIZE]
            logger.debug(f"Fetching chunk {i // CHUNK_SIZE + 1} with {len(chunk)} titles")

            pages_data, redirects = await self.api_client.fetch_pages_batch(chunk, lang)
            all_pages_data.update(pages_data)
            all_redirects.update(redirects)

        return all_pages_data, all_redirects

    async def _fetch_other_language_data(
        self,
        results_map: dict[str, Any],
        primary_data: dict[str, Any],
        redirects: dict[str, str],
        primary_lang: str
    ) -> None:
        """Fetch data for the other language using langlinks."""
        other_lang = "en" if primary_lang == "de" else "de"
        langlinks_map: dict[str, str] = {}

        # Extract langlinks from primary data
        for original_title in results_map.keys():
            lookup_title = redirects.get(original_title, original_title)
            if lookup_title in primary_data:
                page_data = primary_data[lookup_title]
                if "langlinks" in page_data and isinstance(page_data["langlinks"], list):
                    for link in page_data["langlinks"]:
                        if isinstance(link, dict) and link.get("lang") == other_lang:
                            other_title = link.get("*")
                            if other_title:
                                langlinks_map[original_title] = other_title
                                break

        # Fetch other language data if we have langlinks
        if langlinks_map:
            other_lang_titles = list(langlinks_map.values())
            logger.info(f"Found {len(other_lang_titles)} links to {other_lang.upper()} Wikipedia")

            try:
                secondary_data, _ = await self._fetch_language_data(other_lang_titles, other_lang)

                for original_title, other_title in langlinks_map.items():
                    if other_title in secondary_data:
                        try:
                            self.data_processor.merge_page_data(
                                results_map[original_title], secondary_data[other_title], other_lang
                            )
                        except Exception as e:
                            logger.error(f"Error merging {other_lang} data for '{original_title}': {e}")
            except Exception as e:
                logger.error(f"Error fetching {other_lang} language data: {e}")

    async def fetch_pages_dict(
        self, titles: Iterable[str], lang: str = "de", fetch_other_lang: bool = True, try_capitalization: bool = True
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch Wikipedia page information and return as dictionary keyed by title.

        This is a wrapper around fetch_pages that returns data in the format expected
        by the entity linking pipeline.
        """
        logger.debug(f"Fetching pages as dict for {len(list(titles))} titles in language '{lang}'")

        # Convert to list to allow multiple iterations
        title_list = list(titles)

        # Fetch pages using existing method
        pages = await self.fetch_pages(title_list, lang, fetch_other_lang, try_capitalization)

        # Convert to dictionary format
        result = {}

        for original_title in title_list:
            # Find matching page
            matching_page = None
            for page in pages:
                # Check if this page matches the original title
                if (page.title_de and page.title_de.lower() == original_title.lower()) or (
                    page.title_en and page.title_en.lower() == original_title.lower()
                ):
                    matching_page = page
                    break

            if matching_page:
                # Format page data
                page_data = self.data_processor.format_wiki_page(matching_page)
                result[original_title] = page_data
                logger.debug(f"Found Wikipedia data for '{original_title}'")
            else:
                # No page found
                result[original_title] = self.data_processor.create_empty_wikipedia_data(original_title, "not_found")
                logger.debug(f"No Wikipedia data found for '{original_title}'")

        logger.info(
            f"Fetched {len([r for r in result.values() if r.get('status') == 'found'])} of {len(title_list)} pages"
        )
        return result

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "api_client": self.api_client.get_stats(),
        }
