from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_pipeline_happy_path():
    """Test successful pipeline execution with all steps."""
    # Mock the internal HTTP client calls that pipeline makes
    mock_linker_response = {
        "original_text": "Die Zugspitze ist der höchste Berg Deutschlands.",
        "entities": [
            {
                "label": "Zugspitze",
                "type": "MOUNTAIN",
                "wiki_url_de": "https://de.wikipedia.org/wiki/Zugspitze",
                "wiki_url_en": "https://en.wikipedia.org/wiki/Zugspitze"
            }
        ],
        "statistics": {"total_entities": 1}
    }

    mock_compendium_response = {
        "markdown": "## Zugspitze\nDie Zugspitze ist der höchste Berg Deutschlands...",
        "bibliography": "1. https://de.wikipedia.org/wiki/Zugspitze",
        "statistics": {"length": 100}
    }

    mock_qa_response = {
        "qa": [{"question": "Was ist die Zugspitze?", "answer": "Der höchste Berg Deutschlands"}],
        "statistics": {"num_pairs": 1}
    }

    # Mock the httpx client used for internal API calls
    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance

        # Mock the three sequential API calls
        mock_instance.post.side_effect = [
            AsyncMock(status_code=200, json=lambda: mock_linker_response),
            AsyncMock(status_code=200, json=lambda: mock_compendium_response),
            AsyncMock(status_code=200, json=lambda: mock_qa_response)
        ]

        payload = {
            "text": "Die Zugspitze ist der höchste Berg Deutschlands.",
            "config": {
                "linker": {"MODE": "extract", "MAX_ENTITIES": 10},
                "compendium": {"length": 2000},
                "qa": {"num_pairs": 5}
            }
        }

        resp = client.post("/api/v1/pipeline", json=payload)
        assert resp.status_code == 200

        data = resp.json()
        assert "original_text" in data
        assert "linker_output" in data
        assert "compendium_output" in data
        assert "qa_output" in data
        assert "pipeline_statistics" in data


def test_pipeline_empty_text():
    """Test pipeline validation with empty text input."""
    resp = client.post("/api/v1/pipeline", json={"text": ""})
    assert resp.status_code == 422  # Validation error for empty text
