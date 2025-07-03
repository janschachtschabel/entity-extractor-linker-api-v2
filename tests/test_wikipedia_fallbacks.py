"""Tests for Wikipedia fallback strategies."""

import pathlib
import sys
from unittest.mock import AsyncMock, patch

import pytest

# Add project root to path
project_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# Imports after sys.path modification (required for test files)
from app.services.wikipedia.api.client import WikipediaAPIClient  # noqa: E402
from app.services.wikipedia.fallbacks.strategies import WikipediaFallbackStrategies  # noqa: E402
from app.services.wikipedia.models import WikiPage  # noqa: E402


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    return AsyncMock(spec=WikipediaAPIClient)


@pytest.fixture
def fallback_strategies(mock_api_client):
    """Create fallback strategies with mock client."""
    return WikipediaFallbackStrategies(mock_api_client)


class TestWikipediaFallbackStrategies:
    """Test Wikipedia fallback strategies."""

    def test_is_page_complete_valid(self, fallback_strategies):
        """Test page completeness check with valid page."""
        page = WikiPage(
            title_de="Test",
            title_en="Test",
            abstract_de="Test abstract",
            abstract_en="Test abstract",
            wikidata_id="Q123"
        )
        assert fallback_strategies.is_page_complete(page) is True

    def test_is_page_complete_missing_title(self, fallback_strategies):
        """Test page completeness check with missing title."""
        page = WikiPage(
            title_de=None,
            title_en=None,
            abstract_de="Test abstract",
            abstract_en="Test abstract",
            wikidata_id="Q123"
        )
        assert fallback_strategies.is_page_complete(page) is False

    def test_is_page_complete_missing_abstract(self, fallback_strategies):
        """Test page completeness check with missing abstract."""
        page = WikiPage(
            title_de="Test",
            title_en="Test",
            abstract_de=None,
            abstract_en=None,
            wikidata_id="Q123"
        )
        assert fallback_strategies.is_page_complete(page) is False

    def test_is_page_complete_missing_wikidata_id(self, fallback_strategies):
        """Test page completeness check with missing Wikidata ID."""
        page = WikiPage(
            title_de="Test",
            title_en="Test",
            abstract_de="Test abstract",
            abstract_en="Test abstract",
            wikidata_id=None
        )
        assert fallback_strategies.is_page_complete(page) is False

    def test_is_page_complete_none_page(self, fallback_strategies):
        """Test page completeness check with None page."""
        assert fallback_strategies.is_page_complete(None) is False

    def test_generate_name_variations(self, fallback_strategies):
        """Test name variation generation."""
        variations = fallback_strategies._generate_name_variations("München")

        # Should include various transformations
        assert "münchen" in variations  # lowercase
        assert "MÜNCHEN" in variations  # uppercase
        assert "Muenchen" in variations  # umlaut replacement

        # Should not include the original
        assert "München" not in variations

        # Should not have duplicates
        assert len(variations) == len(set(variations))

    def test_generate_name_variations_with_articles(self, fallback_strategies):
        """Test name variation generation with German articles."""
        variations = fallback_strategies._generate_name_variations("Der Bundestag")

        # Should remove German articles
        assert "Bundestag" in variations
        assert "der bundestag" in variations
        assert "DER BUNDESTAG" in variations

    def test_initialization(self, fallback_strategies, mock_api_client):
        """Test that fallback strategies are properly initialized."""
        assert fallback_strategies.api_client == mock_api_client
        assert fallback_strategies.data_processor is not None

    def test_generate_name_variations_special_characters(self, fallback_strategies):
        """Test name variation generation with special characters."""
        variations = fallback_strategies._generate_name_variations("München")

        # Should include umlaut replacement (ü -> ue)
        assert "Muenchen" in variations
        assert "münchen" in variations
        assert "MÜNCHEN" in variations

        # Original should not be included
        assert "München" not in variations

    def test_generate_name_variations_eszett(self, fallback_strategies):
        """Test name variation generation with eszett (ß)."""
        variations = fallback_strategies._generate_name_variations("Weiß")

        # Should replace ß with ss
        assert "Weiss" in variations
        assert "weiß" in variations
        assert "WEISS" in variations

    @pytest.mark.asyncio
    async def test_direct_lookup_success(self, fallback_strategies, mock_api_client):
        """Test successful direct lookup."""
        # Mock successful API response
        mock_page_data = {
            "title": "Berlin",
            "extract": "Hauptstadt Deutschlands",
            "pageid": 12345
        }
        mock_api_client.fetch_pages_batch.return_value = ({"Berlin": mock_page_data}, {})

        # Mock data processor to create WikiPage
        with patch.object(fallback_strategies.data_processor, 'merge_page_data') as mock_merge:
            result = await fallback_strategies.direct_lookup("Berlin", "de")

            assert result is not None
            mock_api_client.fetch_pages_batch.assert_called_once_with(["Berlin"], lang="de")
            mock_merge.assert_called_once()

    @pytest.mark.asyncio
    async def test_direct_lookup_not_found(self, fallback_strategies, mock_api_client):
        """Test direct lookup when entity not found."""
        # Mock empty API response
        mock_api_client.fetch_pages_batch.return_value = ({}, {})

        result = await fallback_strategies.direct_lookup("NonExistent", "de")

        assert result is None
        mock_api_client.fetch_pages_batch.assert_called_once_with(["NonExistent"], lang="de")

    @pytest.mark.asyncio
    async def test_direct_lookup_api_error(self, fallback_strategies, mock_api_client):
        """Test direct lookup with API error."""
        # Mock API error
        mock_api_client.fetch_pages_batch.side_effect = Exception("API Error")

        result = await fallback_strategies.direct_lookup("Berlin", "de")

        assert result is None
        mock_api_client.fetch_pages_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_language_fallback_success(self, fallback_strategies):
        """Test successful language fallback."""
        mock_page = WikiPage(
            title_en="Berlin",
            abstract_en="Capital of Germany",
            wikidata_id="Q64"
        )

        with patch.object(fallback_strategies, 'direct_lookup', return_value=mock_page) as mock_direct:
            result = await fallback_strategies.language_fallback("Berlin", "en")

            assert result is not None
            assert result.title_en == "Berlin"
            mock_direct.assert_called_once_with("Berlin", "en")

    @pytest.mark.asyncio
    async def test_language_fallback_failure(self, fallback_strategies):
        """Test language fallback when lookup fails."""
        with patch.object(fallback_strategies, 'direct_lookup', return_value=None) as mock_direct:
            result = await fallback_strategies.language_fallback("NonExistent", "en")

            assert result is None
            mock_direct.assert_called_once_with("NonExistent", "en")

    @pytest.mark.asyncio
    async def test_opensearch_fallback_capitalization(self, fallback_strategies):
        """Test OpenSearch fallback with capitalization fix."""
        mock_page = WikiPage(
            title_de="Berlin",
            abstract_de="Hauptstadt",
            wikidata_id="Q64"
        )

        with patch.object(fallback_strategies, 'direct_lookup') as mock_direct:
            # Mock is_page_complete to return True for our mock page
            def mock_is_complete(page):
                return page is mock_page

            fallback_strategies.is_page_complete = mock_is_complete

            # First call (original) returns None, second call (capitalized) returns page
            mock_direct.side_effect = [mock_page]  # Only capitalized version succeeds

            result = await fallback_strategies.opensearch_fallback("berlin", "de")

            assert result is not None
            assert result.title_de == "Berlin"
            assert mock_direct.call_count == 1

    @pytest.mark.asyncio
    async def test_opensearch_fallback_no_match(self, fallback_strategies):
        """Test OpenSearch fallback with no matches."""
        with patch.object(fallback_strategies, 'direct_lookup', return_value=None):
            result = await fallback_strategies.opensearch_fallback("CompletelyDifferent", "de")

            assert result is None

    @pytest.mark.asyncio
    async def test_synonym_fallback_success(self, fallback_strategies):
        """Test successful synonym fallback."""
        mock_page = WikiPage(
            title_de="Deutschland",
            abstract_de="Land in Europa",
            wikidata_id="Q183"
        )

        with patch.object(fallback_strategies, '_generate_name_variations', return_value=["Deutschland"]), \
             patch.object(fallback_strategies, 'direct_lookup') as mock_direct, \
             patch.object(fallback_strategies, 'is_page_complete', return_value=True):

            mock_direct.return_value = mock_page

            result = await fallback_strategies.synonym_fallback("Deutschlan", "de")

            assert result is not None
            assert result.title_de == "Deutschland"

    @pytest.mark.asyncio
    async def test_synonym_fallback_no_match(self, fallback_strategies):
        """Test synonym fallback with no matches."""
        with (
            patch.object(fallback_strategies, '_generate_name_variations', return_value=["Variation1", "Variation2"]),
            patch.object(fallback_strategies, 'direct_lookup', return_value=None)
        ):

            result = await fallback_strategies.synonym_fallback("NonExistent", "de")

            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_with_fallbacks_direct_success(self, fallback_strategies):
        """Test fetch with fallbacks - direct lookup succeeds."""
        mock_page = WikiPage(
            title_de="Berlin",
            abstract_de="Hauptstadt",
            wikidata_id="Q64"
        )

        with patch.object(fallback_strategies, 'direct_lookup', return_value=mock_page), \
             patch.object(fallback_strategies, 'is_page_complete', return_value=True):

            result = await fallback_strategies.fetch_with_fallbacks("Berlin", "de", True)

            assert result is not None
            assert result.title_de == "Berlin"

    @pytest.mark.asyncio
    async def test_fetch_with_fallbacks_language_fallback(self, fallback_strategies):
        """Test fetch with fallbacks - language fallback succeeds."""
        mock_page = WikiPage(
            title_en="Berlin",
            abstract_en="Capital",
            wikidata_id="Q64"
        )

        with patch.object(fallback_strategies, 'direct_lookup', return_value=None), \
             patch.object(fallback_strategies, 'language_fallback', return_value=mock_page), \
             patch.object(fallback_strategies, 'is_page_complete', return_value=True):

            result = await fallback_strategies.fetch_with_fallbacks("Berlin", "en", True)

            assert result is not None
            assert result.title_en == "Berlin"

    @pytest.mark.asyncio
    async def test_fetch_with_fallbacks_synonym_success(self, fallback_strategies):
        """Test fetch with fallbacks - synonym fallback succeeds."""
        mock_page = WikiPage(
            title_de="Deutschland",
            abstract_de="Land",
            wikidata_id="Q183"
        )

        with patch.object(fallback_strategies, 'direct_lookup', return_value=None), \
             patch.object(fallback_strategies, 'language_fallback', return_value=None), \
             patch.object(fallback_strategies, 'synonym_fallback', return_value=mock_page), \
             patch.object(fallback_strategies, 'is_page_complete', return_value=True):

            result = await fallback_strategies.fetch_with_fallbacks("Deutschlan", "de", True)

            assert result is not None
            assert result.title_de == "Deutschland"

    @pytest.mark.asyncio
    async def test_fetch_with_fallbacks_opensearch_success(self, fallback_strategies):
        """Test fetch with fallbacks - OpenSearch fallback succeeds."""
        mock_page = WikiPage(
            title_de="Berlin",
            abstract_de="Hauptstadt",
            wikidata_id="Q64"
        )

        with patch.object(fallback_strategies, 'direct_lookup', return_value=None), \
             patch.object(fallback_strategies, 'language_fallback', return_value=None), \
             patch.object(fallback_strategies, 'synonym_fallback', return_value=None), \
             patch.object(fallback_strategies, 'opensearch_fallback', return_value=mock_page), \
             patch.object(fallback_strategies, 'is_page_complete', return_value=True):

            result = await fallback_strategies.fetch_with_fallbacks("berlin", "de", True)

            assert result is not None
            assert result.title_de == "Berlin"

    @pytest.mark.asyncio
    async def test_fetch_with_fallbacks_all_fail(self, fallback_strategies):
        """Test fetch with fallbacks - all strategies fail."""
        with patch.object(fallback_strategies, 'direct_lookup', return_value=None), \
         patch.object(fallback_strategies, 'language_fallback', return_value=None), \
         patch.object(fallback_strategies, 'synonym_fallback', return_value=None), \
         patch.object(fallback_strategies, 'opensearch_fallback', return_value=None):

            result = await fallback_strategies.fetch_with_fallbacks("NonExistent", "de", True)

            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_with_fallbacks_disabled(self, fallback_strategies):
        """Test fetch with fallbacks disabled."""
        mock_page = WikiPage(title_de="Berlin", wikidata_id="Q64")

        with patch.object(fallback_strategies, 'direct_lookup', return_value=mock_page), \
             patch.object(fallback_strategies, 'is_page_complete', return_value=True):

            result = await fallback_strategies.fetch_with_fallbacks("Berlin", "de", False)

            assert result is not None
            assert result.title_de == "Berlin"

    @pytest.mark.asyncio
    async def test_fetch_with_fallbacks_disabled_no_result(self, fallback_strategies):
        """Test fetch with fallbacks disabled and no direct result."""
        with patch.object(fallback_strategies, 'direct_lookup', return_value=None):
            result = await fallback_strategies.fetch_with_fallbacks("NonExistent", "de", False)

            assert result is None
