"""Tests for /compendium endpoint."""

import pathlib
import sys
from unittest.mock import patch

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # after path tweak

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.main import app

client = TestClient(app)


def test_compendium() -> None:
    """Test compendium endpoint with mocked OpenAI response."""
    from unittest.mock import MagicMock

    # Create proper mock response objects
    mock_linker_response = MagicMock()
    mock_linker_response.choices = [MagicMock()]
    mock_linker_response.choices[0].message.content = (
        '[{"label_de": "Zugspitze", "label_en": "Zugspitze", "type": "LOCATION"}]'
    )

    mock_compendium_response = MagicMock()
    mock_compendium_response.choices = [MagicMock()]
    mock_compendium_response.choices[0].message.content = (
        "## Kompendium\n\nDie Zugspitze ist mit 2.962 Metern der höchste Berg Deutschlands "
        "und ein bedeutendes Wahrzeichen der bayerischen Alpen."
    )

    with patch('app.core.openai_wrapper.openai') as mock_openai:
        # Configure mock to return different responses for different calls
        mock_openai.chat.completions.create.side_effect = [mock_linker_response, mock_compendium_response]

        payload_linker = {
            "text": "Die Zugspitze ist der höchste Berg Deutschlands.",
            "config": {"MODE": "extract", "MAX_ENTITIES": 10, "LANGUAGE": "de"},
        }
        resp = client.post("/api/v1/linker", json=payload_linker)
        assert resp.status_code == 200
        linker_response = resp.json()

        compendium_payload = {
            "input_type": "linker_output",
            "linker_data": linker_response,
            "config": {"length": 2000, "enable_citations": True, "educational_mode": True}
        }
        resp2 = client.post("/api/v1/compendium", json=compendium_payload)
        assert resp2.status_code == 200
        md = resp2.json()["markdown"]
        assert "## Kompendium" in md or "Zugspitze" in md
