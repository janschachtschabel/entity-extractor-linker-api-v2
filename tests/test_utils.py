"""Tests for utils endpoints."""

import pathlib
import sys
from unittest.mock import patch

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_split() -> None:
    """Test text splitting endpoint."""
    resp = client.post("/api/v1/utils/split", json={
        "text": "Satz eins. Satz zwei! Satz drei.",
        "chunk_size": 100,
        "overlap": 10,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "chunks" in data


def test_synonyms() -> None:
    """Test synonym generation endpoint."""
    resp = client.post("/api/v1/utils/synonyms", json={"word": "Berg"})
    assert resp.status_code == 200
    data = resp.json()
    assert "synonyms" in data
    assert isinstance(data["synonyms"], list)
    assert len(data["synonyms"]) > 0


def test_translate() -> None:
    """Test translation endpoint."""
    # Test with mocked translation
    with patch('app.core.utils._translate_text') as mock_translate:
        mock_translate.return_value = "Hello"
        resp = client.post("/api/v1/utils/translate", json={
            "text": "Hallo", "target_language": "en"
        })
        assert resp.status_code == 200
        assert resp.json()["translation"] == "Hello"

    # Test with fallback
    with patch('app.core.utils._translate_text', side_effect=Exception("API Error")):
        resp = client.post("/api/v1/utils/translate", json={
            "text": "Hallo", "target_language": "en"
        })
        assert resp.status_code == 200
        # Should return fallback format when translation fails
        assert resp.json()["translation"] == "[en translation of]: Hallo"
