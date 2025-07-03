"""Wikipedia API client for making HTTP requests."""

import asyncio
import json
import random
from typing import Any

import aiohttp
from loguru import logger

from ..constants import MAX_RETRIES, RETRY_DELAY, WIKIPEDIA_API_URL, PageDataMap, RedirectMap
from ..exceptions import WikipediaAPIError, WikipediaAPITimeoutError


class WikipediaAPIClient:
    """Client for making requests to the Wikipedia API."""

    def __init__(self, timeout: float = 30.0):
        """Initialize Wikipedia API client with timeout configuration."""
        self._session: aiohttp.ClientSession | None = None
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._stats = {"requests": 0, "successes": 0, "failures": 0}

    async def __aenter__(self) -> "WikipediaAPIClient":
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self) -> None:
        """Ensure HTTP session is created."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=20,
                ttl_dns_cache=300,
                use_dns_cache=True,
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=self._timeout,
                headers={"User-Agent": "EntityExtractorBatch/1.0 (https://github.com/example/entityextractor)"},
            )

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _update_stats(self, success: bool) -> None:
        """Update request statistics."""
        self._stats["requests"] += 1
        if success:
            self._stats["successes"] += 1
        else:
            self._stats["failures"] += 1

    def get_stats(self) -> dict[str, int]:
        """Get current request statistics."""
        return self._stats.copy()

    async def fetch_pages_batch(
        self, titles: list[str], lang: str = "de", max_retries: int = MAX_RETRIES, base_delay: float = RETRY_DELAY
    ) -> tuple[PageDataMap, RedirectMap]:
        """
        Fetch Wikipedia pages in batch with retry logic.

        Args:
            titles: List of page titles to fetch
            lang: Language code ('de' or 'en')
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff

        Returns:
            Tuple of (pages_data, redirects_map)
        """
        if not titles:
            return {}, {}

        await self._ensure_session()

        # Prepare API parameters
        base_url = WIKIPEDIA_API_URL.format(lang=lang)
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "titles": "|".join(titles),
            "prop": "extracts|pageprops|categories|coordinates|langlinks|links|pageimages",
            "exintro": "true",
            "explaintext": "true",
            "exsectionformat": "plain",
            "redirects": "true",
            "coprimary": "all",
            "cllimit": "max",
            "lllimit": "max",
            "pllimit": "max",
            "piprop": "thumbnail",  # Include thumbnail information
            "pithumbsize": "300",  # Thumbnail size in pixels
        }

        last_exception: Exception | None = None

        # Retry loop with exponential backoff
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    # Calculate delay with exponential backoff and jitter
                    delay = min(
                        base_delay * (2 ** (attempt - 1)) * (0.5 + 0.5 * random.random()),  # noqa: S311
                        60.0,  # Max 60 seconds
                    )
                    logger.warning("Attempt %d/%d failed, retrying in %.1fs...", attempt, max_retries + 1, delay)
                    await asyncio.sleep(delay)

                # Make the API request
                if self._session is None:
                    raise WikipediaAPIError("HTTP session is not initialized")
                async with self._session.get(base_url, params=params) as response:
                    self._update_stats(success=True)
                    logger.debug("Received response with status: %d", response.status)

                    # Handle rate limiting (429 Too Many Requests)
                    if response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", "5"))
                        logger.warning("Rate limited. Waiting %d seconds before retry...", retry_after)
                        await asyncio.sleep(retry_after)
                        continue

                    # Handle other error status codes
                    if response.status >= 400:
                        error_text = await response.text()
                        logger.error(
                            "Wikipedia API error: HTTP %d - %s",
                            response.status,
                            error_text[:500],  # Limit error text length
                        )

                        # Don't retry on client errors (4xx) except 429
                        if 400 <= response.status < 500 and response.status != 429:
                            raise WikipediaAPIError(
                                f"Client error: {response.status} {response.reason}",
                                status_code=response.status,
                                response={"status": response.status, "text": error_text},
                                url=str(response.url),
                                method="GET",
                            )

                        # For server errors, raise to trigger retry
                        response.raise_for_status()

                    # Parse and validate the response
                    try:
                        data = await response.json()
                        logger.debug("Successfully parsed JSON response")

                        # Manual validation of the API response structure
                        if not isinstance(data, dict) or "query" not in data or "pages" not in data["query"]:
                            logger.error(
                                "Wikipedia API response missing 'query' or 'pages'. Raw response (truncated): %s",
                                json.dumps(data)[:2000] if isinstance(data, dict) else str(data)[:2000],
                            )
                            # Gracefully skip this batch and return empty results
                            return {}, {}

                        # Process the response
                        return self._process_api_response(data)

                    except json.JSONDecodeError as e:
                        error_text = await response.text()
                        logger.error(
                            "Failed to decode JSON response. Status: %d. Response: %.500s", response.status, error_text
                        )
                        raise WikipediaAPIError(
                            f"Invalid JSON response: {e}",
                            status_code=response.status,
                            response={"status": response.status, "text": error_text},
                            url=str(response.url),
                            method="GET",
                        ) from e

            except aiohttp.ClientResponseError as e:
                self._update_stats(success=False)
                last_exception = e

                # Don't retry on client errors (4xx) except 429
                if 400 <= e.status < 500 and e.status != 429:
                    raise WikipediaAPIError(
                        f"Client error: {e.status} {e.message}",
                        status_code=e.status,
                        response={"status": e.status, "headers": dict(e.headers or {})},
                        url=str(e.request_info.url) if hasattr(e, "request_info") else None,
                        method=e.request_info.method if hasattr(e, "request_info") else None,
                    ) from e

                # Log and continue to retry
                logger.warning("Server error %d, attempt %d/%d: %s", e.status, attempt + 1, max_retries + 1, str(e))

            except (TimeoutError, aiohttp.ClientError) as e:
                self._update_stats(success=False)
                last_exception = e
                logger.warning("Network error (attempt %d/%d): %s", attempt + 1, max_retries + 1, str(e))

            except Exception as e:
                self._update_stats(success=False)
                last_exception = e
                logger.error(
                    "Unexpected error (attempt %d/%d): %s", attempt + 1, max_retries + 1, str(e), exc_info=True
                )

        # If we get here, all retries failed
        if isinstance(last_exception, asyncio.TimeoutError):
            timeout_val = float(self._timeout.total) if self._timeout.total is not None else 30.0
            raise WikipediaAPITimeoutError(timeout=timeout_val, url=base_url) from last_exception
        elif last_exception:
            raise WikipediaAPIError(
                f"All {max_retries + 1} attempts failed", response={"last_error": str(last_exception)}
            ) from last_exception
        else:
            raise WikipediaAPIError("Unknown error occurred during API request")

    def _process_api_response(self, data: dict[str, Any]) -> tuple[PageDataMap, RedirectMap]:
        """Process Wikipedia API response data."""
        pages_data: PageDataMap = {}
        redirects_map: RedirectMap = {}

        # Handle redirects
        if data.get("query", {}).get("redirects"):
            for redirect in data["query"]["redirects"]:
                if isinstance(redirect, dict) and "from" in redirect and "to" in redirect:
                    from_title = str(redirect["from"])
                    to_title = str(redirect["to"])
                    redirects_map[from_title] = to_title
                    logger.debug("Redirect: %s → %s", from_title, to_title)

        # Process pages
        pages = data["query"]["pages"]
        # Handle both dict and list for 'pages'
        if isinstance(pages, list):
            # Convert list to dict keyed by pageid as string (or fallback to title if missing)
            try:
                pages = {str(page["pageid"]): page for page in pages if "pageid" in page}
            except Exception as e:
                logger.error(
                    "Failed to convert 'pages' list to dict: {err}. Raw 'pages': {pages!r}", err=str(e), pages=pages
                )
                return {}, redirects_map

        if not isinstance(pages, dict):
            logger.error(
                "Wikipedia API 'pages' is not a dict even after conversion: {pages!r}. Raw 'pages' (truncated): {raw}",
                pages=pages,
                raw=json.dumps(pages)[:2000] if isinstance(pages, dict | list) else str(pages)[:2000],
            )
            return {}, redirects_map

        for page_id, page_data in pages.items():
            try:
                # Skip special pages (negative page IDs)
                if str(page_id).startswith("-"):
                    logger.warning("Skipping special page with ID: %s", page_id)
                    continue

                title = page_data.get("title")
                if not title:
                    logger.warning("Page with ID %s has no title, skipping", page_id)
                    continue

                logger.debug("Processing page: %s (ID: %s)", title, page_id)

                # Store the page data
                pages_data[str(title)] = page_data

            except Exception as e:
                logger.error("Error processing page %s: %s", page_id, e, exc_info=True)
                continue

        logger.info("Successfully processed %d pages and %d redirects", len(pages_data), len(redirects_map))
        return pages_data, redirects_map
