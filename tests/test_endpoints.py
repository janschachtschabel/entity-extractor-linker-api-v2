"""Basic integration tests for FastAPI endpoints.

Executed with `pytest`. Uses FastAPI's built-in `TestClient` (requests based)
so no additional HTTP client dependency is required.
"""

import pathlib
import sys

from fastapi.testclient import TestClient

from app.main import app

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

client = TestClient(app)


def test_health() -> None:
    """`/health` returns JSON with status, service, version and timestamp."""
    resp = client.get("/health")
    assert resp.status_code == 200
    json_resp = resp.json()
    assert json_resp["status"] == "healthy"
    assert json_resp["service"] == "entityextractorbatch"
    assert "version" in json_resp
    assert "timestamp" in json_resp


def test_linker_mock() -> None:
    """`/api/v1/linker` returns one mock entity for Zugspitze text."""
    from unittest.mock import patch

    from app.models.entity import Entity

    # Create a mock entity using the correct Entity constructor
    mock_entity = Entity(
        label="Zugspitze",
        type="LOCATION",
        wiki_url_de="https://de.wikipedia.org/wiki/Zugspitze",
        wiki_url_en="https://en.wikipedia.org/wiki/Zugspitze",
        abstract_de=("Die Zugspitze ist mit 2962 m ü. NHN der höchste "
                   "Gipfel des Wettersteingebirges und gleichzeitig "
                   "Deutschlands höchster Berg."),
        abstract_en=("The Zugspitze is the highest peak of the "
                   "Wetterstein Mountains and the highest mountain in Germany."),
        categories=[],
        internal_links=[],
        status="linked"
    )

    # Mock the process_text function to return our mock entity
    with patch('app.core.linker.process_text') as mock_process_text:
        # Mock the return value of process_text
        mock_process_text.return_value = (
            [mock_entity],
            {"total_entities": 1}
        )

        payload = {
            "text": "Die Zugspitze ist der höchste Berg Deutschlands.",
            "config": {"MODE": "extract", "MAX_ENTITIES": 10, "LANGUAGE": "de"},
        }
        resp = client.post("/api/v1/linker", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["original_text"].startswith("Die Zugspitze")
        assert data["statistics"]["total_entities"] >= 1
        entity = data["entities"][0]
        # The entity structure has 'entity', 'details', 'sources', 'id' fields
        assert "entity" in entity
        assert "details" in entity
        assert "sources" in entity
        assert "id" in entity
        # Just check that we have some entity data
        assert entity["entity"] is not None
