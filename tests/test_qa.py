"""Tests for /qa endpoint and core QA functionality."""

import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
project_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# Imports after sys.path modification (required for test files)
from fastapi.testclient import TestClient  # noqa: E402

from app.core.qa import generate_qa_pairs  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def test_qa_endpoint_basic() -> None:
    """Test QA endpoint with basic valid input."""
    resp = client.post("/api/v1/qa", json={
        "text": "## Zugspitze\nDie Zugspitze ist der höchste Berg Deutschlands mit 2962 Metern Höhe.",
        "num_pairs": 3
    })
    assert resp.status_code == 200
    assert len(resp.json()["qa"]) >= 1


def test_qa_endpoint_with_topic() -> None:
    """Test QA endpoint with topic parameter."""
    resp = client.post("/api/v1/qa", json={
        "text": "## Geographie\nBerge sind wichtige geografische Formationen.",
        "num_pairs": 2,
        "topic": "Geographie"
    })
    assert resp.status_code == 200
    assert "qa" in resp.json()


def test_qa_endpoint_with_max_chars() -> None:
    """Test QA endpoint with max_chars parameter."""
    resp = client.post("/api/v1/qa", json={
        "text": "## Test\nLanger Text für QA-Generierung mit Längenbegrenzung.",
        "num_pairs": 1,
        "max_chars": 50
    })
    assert resp.status_code == 200
    assert "qa" in resp.json()


def test_qa_endpoint_empty_text() -> None:
    """Test QA endpoint with empty text."""
    resp = client.post("/api/v1/qa", json={
        "text": "",
        "num_pairs": 1
    })
    assert resp.status_code == 422  # Validation error


def test_qa_endpoint_invalid_num_pairs() -> None:
    """Test QA endpoint with invalid num_pairs."""
    resp = client.post("/api/v1/qa", json={
        "text": "Test text",
        "num_pairs": 0
    })
    assert resp.status_code == 422  # Validation error


# Core QA function tests
@patch('app.core.openai_wrapper.openai')
@patch('app.core.openai_wrapper._ensure_ready')
def test_generate_qa_pairs_basic(mock_ensure_ready, mock_openai) -> None:
    """Test basic QA generation functionality."""
    mock_ensure_ready.return_value = None
    mock_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(
            content="Was ist die Zugspitze?;Der höchste Berg Deutschlands\nWo liegt die Zugspitze?;In den Alpen"
        ))
    ]

    result = generate_qa_pairs(
        "Die Zugspitze ist der höchste Berg Deutschlands mit 2962 Metern.",
        num_pairs=2
    )

    assert len(result) == 2
    assert result[0][0] == "Was ist die Zugspitze?"
    assert result[0][1] == "Der höchste Berg Deutschlands"


@patch('app.core.openai_wrapper.openai')
@patch('app.core.openai_wrapper._ensure_ready')
def test_generate_qa_pairs_with_topic(mock_ensure_ready, mock_openai) -> None:
    """Test QA generation with specific topic."""
    mock_ensure_ready.return_value = None
    mock_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Was ist Geographie?;Die Wissenschaft der Erde"))
    ]

    result = generate_qa_pairs(
        "Geographie ist die Wissenschaft der Erde.",
        num_pairs=1,
        topic="Geographie"
    )

    assert len(result) == 1
    assert "Geographie" in result[0][0] or "Geographie" in result[0][1]


@patch('app.core.openai_wrapper.openai')
@patch('app.core.openai_wrapper._ensure_ready')
def test_generate_qa_pairs_with_max_chars(mock_ensure_ready, mock_openai) -> None:
    """Test QA generation with character limit."""
    mock_ensure_ready.return_value = None
    mock_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Kurze Frage?;Kurze Antwort"))
    ]

    result = generate_qa_pairs(
        "Test text for character limit.",
        num_pairs=1,
        max_chars=20
    )

    assert len(result) == 1
    # Check that answers respect character limit (approximately)
    assert len(result[0][1]) <= 30  # Some tolerance


@patch('app.core.openai_wrapper.openai', None)
@patch('app.core.openai_wrapper._ensure_ready')
def test_generate_qa_pairs_openai_none(mock_ensure_ready) -> None:
    """Test QA generation when OpenAI client is None."""
    mock_ensure_ready.return_value = None

    with pytest.raises(RuntimeError, match="OpenAI-Client ist nicht initialisiert"):
        generate_qa_pairs("Test text", num_pairs=1)


@patch('app.core.openai_wrapper.openai')
@patch('app.core.openai_wrapper._ensure_ready')
def test_generate_qa_pairs_openai_error(mock_ensure_ready, mock_openai) -> None:
    """Test QA generation when OpenAI API fails."""
    mock_ensure_ready.return_value = None
    mock_openai.chat.completions.create.side_effect = Exception("API Error")

    with pytest.raises(RuntimeError, match="QA generation failed"):
        generate_qa_pairs("Test text", num_pairs=1)


@patch('app.core.openai_wrapper.openai')
@patch('app.core.openai_wrapper._ensure_ready')
def test_generate_qa_pairs_empty_response(mock_ensure_ready, mock_openai) -> None:
    """Test QA generation with empty OpenAI response."""
    mock_ensure_ready.return_value = None
    mock_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=""))
    ]

    with pytest.raises(ValueError, match="OpenAI returned empty or invalid response"):
        generate_qa_pairs("Test text", num_pairs=1)


@patch('app.core.openai_wrapper.openai')
@patch('app.core.openai_wrapper._ensure_ready')
def test_generate_qa_pairs_malformed_response(mock_ensure_ready, mock_openai) -> None:
    """Test QA generation with malformed OpenAI response."""
    mock_ensure_ready.return_value = None
    mock_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Invalid format without semicolon"))
    ]

    # Should raise ValueError when no valid pairs can be extracted
    with pytest.raises(ValueError, match="OpenAI returned empty or invalid response"):
        generate_qa_pairs("Test text", num_pairs=1)


@patch('app.core.openai_wrapper.openai')
@patch('app.core.openai_wrapper._ensure_ready')
def test_generate_qa_pairs_partial_response(mock_ensure_ready, mock_openai) -> None:
    """Test QA generation with partially valid response."""
    mock_ensure_ready.return_value = None
    mock_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Valid question?;Valid answer\nInvalid line without semicolon"))
    ]

    result = generate_qa_pairs("Test text", num_pairs=2)
    # Should extract valid pairs and skip invalid ones
    assert len(result) >= 1
    assert result[0][0] == "Valid question?"
    assert result[0][1] == "Valid answer"
