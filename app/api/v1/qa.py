"""QA endpoint `/qa` - generates question/answer pairs from compendium."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1", tags=["qa"])


class QARequest(BaseModel):
    """Request model for QA generation endpoint."""

    text: str = Field(  # type: ignore[call-overload]
        ...,
        min_length=1,
        description="Text content for QA generation (supports compendium markdown)",
        example="Was ist ein Planet im Weltall?"
    )
    num_pairs: int = Field(  # type: ignore[call-overload]
        10,
        ge=1,
        le=20,
        example=5
    )
    max_answer_length: int = Field(  # type: ignore[call-overload]
        250,
        ge=50,
        le=1000,
        example=200
    )
    level_property: str | None = Field(
        None, description="Name der Bildungsstufen-Eigenschaft (z.B. 'Bildungsstufe')"
    )
    level_values: list[str] | None = Field(
        None, description="Liste der Bildungsstufen-Werte (z.B. ['Schule', 'Hochschule', 'Berufsbildung'])"
    )


class QAPair(BaseModel):
    """Represents a question-answer pair with educational level metadata."""

    question: str
    answer: str
    # Neue Felder für Bildungsstufen
    level_property: str | None = Field(None, description="Name der Bildungsstufen-Eigenschaft")
    level_value: str | None = Field(None, description="Zugewiesene Bildungsstufe für dieses QA-Paar")


class QAResponse(BaseModel):
    """Response containing generated QA pairs."""

    original_text: str
    qa: list[QAPair]


@router.post("/qa", response_model=QAResponse)
async def qa_endpoint(payload: QARequest) -> QAResponse:
    """Generate question-answer pairs from text content with optional educational level distribution.

    This endpoint uses OpenAI to generate educational QA pairs from the provided
    text content. Supports standard QA generation and advanced educational level
    distribution across German educational system levels or Bloom's Taxonomy.

    Features:
    - Standard QA pair generation
    - Educational level distribution (German Bildungsstufen)
    - Bloom's Taxonomy cognitive levels
    - Custom taxonomies and categories
    - Automatic even distribution across specified levels
    - Level-appropriate language and complexity adaptation

    Parameters
    ----------
    payload : QARequest
        Request containing:
        - text: Input text (markdown supported)
        - num_pairs: Number of QA pairs (1-20)
        - max_answer_length: Maximum answer length (50-1000 chars)
        - level_property: Optional property name (e.g., 'Bildungsstufe')
        - level_values: Optional list of educational levels

    Educational Levels (German Standard):
    - Elementarbereich, Primarstufe, Sekundarstufe I, Sekundarstufe II,
      Hochschule, Berufliche Bildung, Erwachsenenbildung, Förderschule

    Bloom's Taxonomy Levels:
    - Erinnern, Verstehen, Anwenden, Analysieren, Bewerten, Erschaffen

    Returns
    -------
    QAResponse
        Response containing:
        - original_text: Input text
        - qa: List of QA pairs with optional level metadata

    Raises
    ------
    HTTPException
        400: If text is empty or invalid parameters
        503: If OpenAI service is unavailable or misconfigured
        500: If QA generation fails for other reasons

    Examples
    --------
    Standard QA generation:
    ```json
    {
      "text": "Einstein developed relativity theory...",
      "num_pairs": 5
    }
    ```

    Educational levels distribution:
    ```json
    {
      "text": "Quantum physics content...",
      "num_pairs": 12,
      "level_property": "Bildungsstufe",
      "level_values": ["Sekundarstufe I", "Sekundarstufe II", "Hochschule"]
    }
    ```
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="text required")

    from ...core import qa as qa_core

    try:
        # Prüfe ob Bildungsstufen-Konfiguration vollständig ist
        if payload.level_property and payload.level_values:
            # Generiere QA-Paare mit Bildungsstufen-Verteilung
            pairs_with_levels = qa_core.generate_qa_pairs_with_levels(
                payload.text,
                payload.num_pairs,
                max_chars=payload.max_answer_length,
                level_property=payload.level_property,
                level_values=payload.level_values
            )
            qa_pairs = [
                QAPair(
                    question=q,
                    answer=a,
                    level_property=level_prop,
                    level_value=level_val
                )
                for q, a, level_prop, level_val in pairs_with_levels
            ]
        else:
            # Standard QA-Generierung ohne Bildungsstufen
            pairs = qa_core.generate_qa_pairs(payload.text, payload.num_pairs, max_chars=payload.max_answer_length)
            qa_pairs = [QAPair(question=q, answer=a, level_property=None, level_value=None) for q, a in pairs]

        import logging
        logging.getLogger("uvicorn.error").debug(f"QA-Endpoint: payload.text={payload.text!r}")
        return QAResponse(original_text=payload.text, qa=qa_pairs)
    except RuntimeError as e:
        # OpenAI configuration or availability issues
        raise HTTPException(status_code=503, detail=f"QA generation service unavailable: {e!s}") from e
    except ValueError as e:
        # Invalid or empty OpenAI response
        raise HTTPException(status_code=500, detail=f"QA generation failed: {e!s}") from e
    except Exception as e:
        # Unexpected errors
        raise HTTPException(status_code=500, detail=f"Unexpected error during QA generation: {e!s}") from e
