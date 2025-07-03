"""Tests for Wikipedia service."""

import re
from urllib.parse import quote

from aioresponses import aioresponses
import pytest

from app.services.wikipedia.service import WikipediaService


@pytest.mark.asyncio
async def test_fetch_single_basic_fields():
    """Test basic Wikipedia page fetching functionality."""
    title = "Albert Einstein"

    # Mock response for English Wikipedia
    en_api_resp = {
        "query": {
            "pages": {
                "736": {
                    "pageid": 736,
                    "ns": 0,
                    "title": title,
                    "extract": "Albert Einstein was a German-born theoretical physicist...",
                    "pageprops": {
                        "wikibase_item": "Q937",
                        "infoboxes": ["scientist"]
                    },
                    "coordinates": [
                        {
                            "lat": 52.5,
                            "lon": 13.4,
                            "primary": "",
                            "globe": "earth"
                        }
                    ],
                    "categories": [
                        {"title": "Category:German physicists"}
                    ],
                    "links": [
                        {"title": "Physics"},
                        {"title": "Relativity"}
                    ],
                    "pageimage": "Einstein_1921.jpg"
                }
            }
        }
    }

    with aioresponses() as mock:
        en_url_re = re.compile(r"https://en\.wikipedia\.org/w/api\.php.*")
        mock.get(en_url_re, payload=en_api_resp, status=200)

        # Mock German Wikipedia API (empty response)
        de_url_re = re.compile(r"https://de\.wikipedia\.org/w/api\.php.*")
        de_api_resp = {"query": {"pages": {}}}
        mock.get(de_url_re, payload=de_api_resp, status=200)

        # Test the service
        async with WikipediaService() as svc:
            pages = await svc.fetch_pages([title], lang="en")

    assert len(pages) == 1
    page = pages[0]

    # Basic assertions
    assert page.title_en == title
    assert page.abstract_en is not None
    assert "theoretical physicist" in page.abstract_en
    assert page.wikidata_id == "Q937"

    # Coordinate assertions
    assert page.lat == 52.5 and page.lon == 13.4

    # URL assertions
    assert page.wiki_url_en is not None
    if page.wiki_url_en:
        assert page.wiki_url_en.endswith(quote(title.replace(" ", "_")))

    # German title might be None if no langlink was found
    # For this test, we don't strictly enforce it since our mock doesn't provide German data


@pytest.mark.asyncio
async def test_handles_http_error():
    """Test error handling for HTTP failures."""
    title = "Error Case"

    with aioresponses() as mock:
        # Mock both APIs to return 500 errors
        en_url_re = re.compile(r"https://en\.wikipedia\.org/w/api\.php.*")
        mock.get(en_url_re, status=500)

        de_url_re = re.compile(r"https://de\.wikipedia\.org/w/api\.php.*")
        mock.get(de_url_re, status=500)

        # Expect WikipediaAPIError to be raised
        from app.services.wikipedia.exceptions import WikipediaAPIError
        with pytest.raises(WikipediaAPIError):
            async with WikipediaService() as svc:
                await svc.fetch_pages([title], lang="en")
