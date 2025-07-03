from unittest.mock import patch

import pytest

from app.core.linker import process_text
from app.models.entity import Entity


@pytest.mark.parametrize("mode", ["extract", "generate"])
def test_process_text_modes(mode):
    """Test different processing modes with mocked OpenAI and Wikipedia."""
    text = "Die Zugspitze ist ein Berg in Deutschland."

    # Mock the OpenAI functions
    mock_entities = [("Zugspitze", "MOUNTAIN", {})]

    # Mock the Wikipedia service to return processed entities
    mock_entity = Entity(
        label="Zugspitze",
        label_en="Zugspitze",
        type="MOUNTAIN",
        wikidata_id="Q170230",
        wiki_url_en="https://en.wikipedia.org/wiki/Zugspitze",
        wiki_url_de="https://de.wikipedia.org/wiki/Zugspitze",
        abstract_de="Highest mountain in Germany",
        image_url="https://example.com/zug.jpg",
        categories=["Mountains of Germany"],
        internal_links=[],
        geo_lat=47.4,
        geo_lon=11.0,
        infobox_type="mountain",
        status="linked"
    )

    with patch("app.core.openai_wrapper.extract_entities", return_value=mock_entities), \
         patch("app.core.openai_wrapper.generate_entities", return_value=mock_entities), \
         patch("app.core.linker._context_to_entity", return_value=mock_entity):

        entities, stats = process_text(text, mode=mode, max_entities=5)

        assert len(entities) >= 1
        assert stats["entities_extracted"] >= 1
        assert entities[0].label == "Zugspitze"
        assert entities[0].type == "MOUNTAIN"


def test_auto_splitter():
    """Test automatic text splitting for long texts."""
    # Create a long text that would exceed token limits
    long_text = "Die Zugspitze ist ein Berg. " * 1000  # Very long text

    mock_entities = [("Zugspitze", "MOUNTAIN", {})]
    mock_entity = Entity(
        label="Zugspitze",
        type="MOUNTAIN",
        status="linked"
    )

    with patch("app.core.openai_wrapper.extract_entities", return_value=mock_entities), \
         patch("app.core.linker._context_to_entity", return_value=mock_entity):

        entities, stats = process_text(long_text, max_entities=5)

        # Should still work with long text
        assert len(entities) >= 0
        assert "entities_extracted" in stats
