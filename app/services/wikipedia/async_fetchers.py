"""Low-level async HTTP helpers for WikipediaService.

Isolated here to avoid circular imports and to keep `service.py` compact.
"""

from __future__ import annotations

import urllib.parse

import aiohttp
from loguru import logger

WIKIPEDIA_API_URL = "https://{lang}.wikipedia.org/w/api.php"

__all__ = ["get_redirect_targets", "open_search"]


async def get_redirect_targets(title: str, *, lang: str, session: aiohttp.ClientSession) -> list[str]:
    """Return titles that *title* redirects to (max 5)."""
    params = {
        "action": "query",
        "titles": title,
        "redirects": 1,
        "rdlimit": 5,
        "format": "json",
    }
    url = WIKIPEDIA_API_URL.format(lang=lang) + "?" + urllib.parse.urlencode(params)
    logger.debug("Redirect query %s", url)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            rds = data.get("query", {}).get("redirects", [])
            return [rd.get("to", "").replace(" ", "_") for rd in rds][:5]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# HTML crawler fallback
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# OpenSearch
# ---------------------------------------------------------------------------


async def open_search(term: str, *, lang: str, session: aiohttp.ClientSession) -> list[str]:
    """Use MediaWiki *OpenSearch* API to suggest alternative page titles.

    Returns a list of candidate titles (URL-encoded with underscores). If the
    request fails or returns no candidates, an empty list is returned.
    """
    params = {
        "action": "opensearch",
        "search": term,
        "limit": "5",
        "namespace": "0",
        "format": "json",
    }
    url = WIKIPEDIA_API_URL.format(lang=lang) + "?" + urllib.parse.urlencode(params)
    logger.debug("OpenSearch request %s", url)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                logger.info("OpenSearch HTTP %s for %s", resp.status, term)
                return []
            data = await resp.json()
            # data[1] is list of suggestions (space titles)
            suggestions = data[1] if isinstance(data, list) and len(data) > 1 else []
            return [s.replace(" ", "_") for s in suggestions]
    except Exception as exc:  # pylint: disable=broad-except
        logger.info("OpenSearch failed for %s: %s", term, exc)
        return []
