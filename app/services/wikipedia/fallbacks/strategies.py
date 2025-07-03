"""Fallback strategies for Wikipedia entity linking."""

from __future__ import annotations

from loguru import logger

from ..api.client import WikipediaAPIClient
from ..models import WikiPage
from ..utils.data_processor import WikipediaDataProcessor


class WikipediaFallbackStrategies:
    """Collection of fallback strategies for Wikipedia entity linking."""

    def __init__(self, api_client: WikipediaAPIClient) -> None:
        """Initialize fallback strategies with API client and data processor."""
        self.api_client = api_client
        self.data_processor = WikipediaDataProcessor()

    def is_page_complete(self, page: WikiPage) -> bool:
        """Check if a WikiPage has sufficient data for linking."""
        return bool(
            page and (page.title_de or page.title_en) and (page.abstract_de or page.abstract_en)
        )

    async def direct_lookup(self, entity_name: str, lang: str) -> WikiPage | None:
        """
        Direct lookup for an entity in the specified language.

        Args:
            entity_name: Entity name to search for
            lang: Language to search in ('de' or 'en')

        Returns:
            WikiPage if found, None otherwise
        """
        logger.debug(f"[DIRECT] Looking up '{entity_name}' in {lang}")

        try:
            # Fetch single page using API client
            pages_data, redirects = await self.api_client.fetch_pages_batch([entity_name], lang=lang)

            # Check if we found data
            final_title = redirects.get(entity_name, entity_name)
            if final_title in pages_data:
                # Create WikiPage and merge data
                wiki_page = WikiPage()
                self.data_processor.merge_page_data(wiki_page, pages_data[final_title], lang)

                logger.debug(f"[DIRECT] Found '{entity_name}' -> '{final_title}' in {lang}")
                return wiki_page
            else:
                logger.debug(f"[DIRECT] No data found for '{entity_name}' in {lang}")
                return None

        except Exception as e:
            logger.error(f"[DIRECT] Error in direct lookup for '{entity_name}': {e}")
            return None

    async def language_fallback(self, entity_name: str, lang: str) -> WikiPage | None:
        """
        Try to find the entity in the specified language.

        Args:
            entity_name: Entity name to search for
            lang: Language to search in ('de' or 'en')

        Returns:
            WikiPage if found, None otherwise
        """
        logger.debug(f"[FALLBACK] Language fallback for '{entity_name}' in {lang}")

        try:
            # Use direct lookup in the fallback language
            return await self.direct_lookup(entity_name, lang)
        except Exception as e:
            logger.error(f"Language fallback failed for '{entity_name}': {e}")
            return None

    async def opensearch_fallback(self, entity_name: str, lang: str) -> WikiPage | None:
        """
        Use Wikipedia OpenSearch API to find similar titles.

        Args:
            entity_name: Entity name to search for
            lang: Language to search in

        Returns:
            WikiPage if found, None otherwise
        """
        logger.debug(f"[FALLBACK] OpenSearch fallback for '{entity_name}' in {lang}")

        try:
            # For now, try a simple capitalization fix as basic "search"
            # This could be extended to use the actual OpenSearch API
            capitalized = entity_name.title()
            if capitalized != entity_name:
                logger.debug(f"[FALLBACK] Trying capitalized version: '{capitalized}'")
                page = await self.direct_lookup(capitalized, lang)
                if page and self.is_page_complete(page):
                    logger.info(f"[FALLBACK] Found '{entity_name}' via capitalization '{capitalized}'")
                    return page

            # Try lowercase version
            lowercase = entity_name.lower()
            if lowercase != entity_name:
                logger.debug(f"[FALLBACK] Trying lowercase version: '{lowercase}'")
                page = await self.direct_lookup(lowercase, lang)
                if page and self.is_page_complete(page):
                    logger.info(f"[FALLBACK] Found '{entity_name}' via lowercase '{lowercase}'")
                    return page

            logger.debug(f"[FALLBACK] OpenSearch fallback found nothing for '{entity_name}'")
            return None
        except Exception as e:
            logger.error(f"OpenSearch fallback failed for '{entity_name}': {e}")
            return None

    async def synonym_fallback(self, entity_name: str, lang: str) -> WikiPage | None:
        """
        Try common variations and synonyms of the entity name.

        Args:
            entity_name: Entity name to search for
            lang: Language to search in

        Returns:
            WikiPage if found, None otherwise
        """
        logger.debug(f"[FALLBACK] Synonym fallback for '{entity_name}' in {lang}")

        try:
            # First try simple variations (fast)
            variations = self._generate_name_variations(entity_name)

            for variation in variations:
                logger.debug(f"[FALLBACK] Trying variation: '{variation}'")
                page = await self.direct_lookup(variation, lang)
                if page and self.is_page_complete(page):
                    logger.info(f"[FALLBACK] Found '{entity_name}' via variation '{variation}'")
                    return page

            # If simple variations failed, try intelligent synonyms (slower but more effective)
            logger.debug(f"[FALLBACK] Trying intelligent synonym generation for '{entity_name}'")
            try:
                from app.core.utils import generate_synonyms

                intelligent_synonyms = generate_synonyms(entity_name, max_synonyms=3, lang=lang)

                for synonym in intelligent_synonyms:
                    logger.debug(f"[FALLBACK] Trying intelligent synonym: '{synonym}'")
                    page = await self.direct_lookup(synonym, lang)
                    if page and self.is_page_complete(page):
                        logger.info(f"[FALLBACK] Found '{entity_name}' via intelligent synonym '{synonym}'")
                        return page

            except Exception as e:
                logger.warning(f"[FALLBACK] Intelligent synonym generation failed for '{entity_name}': {e}")

            logger.debug(f"[FALLBACK] No variations or synonyms found for '{entity_name}'")
            return None
        except Exception as e:
            logger.error(f"Synonym fallback failed for '{entity_name}': {e}")
            return None



    async def fetch_with_fallbacks(
        self, entity_name: str, lang: str = "de", enable_fallbacks: bool = True
    ) -> WikiPage | None:
        """
        Fetch Wikipedia page with multiple fallback strategies.

        Args:
            entity_name: Entity name to search for
            lang: Primary language to search in
            enable_fallbacks: Whether to use fallback strategies

        Returns:
            WikiPage if found, None otherwise
        """
        logger.debug(f"Fetching '{entity_name}' with fallbacks enabled: {enable_fallbacks}")

        # Strategy 1: Direct lookup
        try:
            page = await self.direct_lookup(entity_name, lang)
            if page and self.is_page_complete(page):
                logger.info(f"Found '{entity_name}' via direct lookup")
                return page
        except Exception as e:
            logger.warning(f"Direct lookup failed for '{entity_name}': {e}")

        if not enable_fallbacks:
            return None

        # Strategy 2: Language fallback (if not primary language)
        if lang != "de":  # Try German if we're not already searching in German
            try:
                page = await self.language_fallback(entity_name, "de")
                if page and self.is_page_complete(page):
                    logger.info(f"Found '{entity_name}' via German fallback")
                    return page
            except Exception as e:
                logger.warning(f"German fallback failed for '{entity_name}': {e}")

        # Strategy 3: Synonym/variation fallback
        try:
            page = await self.synonym_fallback(entity_name, lang)
            if page and self.is_page_complete(page):
                logger.info(f"Found '{entity_name}' via synonym fallback")
                return page
        except Exception as e:
            logger.warning(f"Synonym fallback failed for '{entity_name}': {e}")

        # Strategy 4: OpenSearch fallback
        try:
            page = await self.opensearch_fallback(entity_name, lang)
            if page and self.is_page_complete(page):
                logger.info(f"Found '{entity_name}' via OpenSearch fallback")
                return page
        except Exception as e:
            logger.warning(f"OpenSearch fallback failed for '{entity_name}': {e}")

        logger.warning(f"All fallback strategies failed for '{entity_name}'")
        return None

    def _generate_name_variations(self, entity_name: str) -> list[str]:
        """Generate common variations of an entity name."""
        variations = []

        # Capitalization variations
        variations.append(entity_name.title())
        variations.append(entity_name.lower())
        variations.append(entity_name.upper())

        # Remove common prefixes/suffixes
        if entity_name.startswith("Der "):
            variations.append(entity_name[4:])
        if entity_name.startswith("Die "):
            variations.append(entity_name[4:])
        if entity_name.startswith("Das "):
            variations.append(entity_name[4:])

        # Replace common characters
        variations.append(entity_name.replace("ß", "ss"))
        variations.append(entity_name.replace("ä", "ae"))
        variations.append(entity_name.replace("ö", "oe"))
        variations.append(entity_name.replace("ü", "ue"))

        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for var in variations:
            if var not in seen and var != entity_name:
                seen.add(var)
                unique_variations.append(var)

        return unique_variations
