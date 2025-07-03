"""Tests for /compendium endpoint."""

import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

import pathlib
import sys

from fastapi.testclient import TestClient  # after path tweak

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.main import app

client = TestClient(app)


def test_compendium() -> None:
    """Test compendium endpoint with mocked OpenAI response."""
    payload_linker = {
        "text": "Die Zugspitze ist der höchste Berg Deutschlands.",
        "config": {"MODE": "extract", "MAX_ENTITIES": 10, "LANGUAGE": "de"},
    }
    resp = client.post("/api/v1/linker", json=payload_linker)
    assert resp.status_code == 200
    linker_response = resp.json()
    print("\n--- Linker Response ---\n", linker_response, "\n----------------\n")

    compendium_payload = {
        "input_type": "linker_output",
        "linker_data": linker_response,
        "config": {"length": 2000, "enable_citations": True, "educational_mode": True}
    }
    resp2 = client.post("/api/v1/compendium", json=compendium_payload)
    assert resp2.status_code == 200
    md = resp2.json()["markdown"]
    print("\n--- Kompendium-Output ---\n", md, "\n------------------------\n")
    assert "## Kompendium" in md or "Zugspitze" in md
