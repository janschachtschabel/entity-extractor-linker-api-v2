"""Misc utility endpoints: split, synonyms, translate."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...core import utils as utils_core

router = APIRouter(prefix="/v1/utils", tags=["utils"])


# --- Split text -----------------------------------------------------------
class SplitRequest(BaseModel):
    """Request payload for text splitting endpoint."""

    text: str = Field(..., min_length=1)
    chunk_size: int = Field(1000, ge=10, le=5000)
    overlap: int = Field(50, ge=0, le=500)
    split_by: str = Field("sentence", pattern="^(sentence|char)$")


class SplitResponse(BaseModel):
    """Response containing text chunks."""

    chunks: list[str]


@router.post("/split", response_model=SplitResponse)
async def split_text_endpoint(payload: SplitRequest) -> SplitResponse:
    """Split text into chunks with configurable size, overlap, and splitting strategy.

    This endpoint intelligently splits long text into manageable chunks for processing,
    analysis, or feeding into language models with context preservation options.

    ## Parameters:

    **text** (required):
    - The text content to be split into chunks
    - Can be any length from short paragraphs to long documents
    - Whitespace is automatically trimmed

    **chunk_size** (10-5000, default: 1000):
    - Target size of each chunk in characters
    - Actual chunk sizes may vary slightly depending on split_by strategy
    - Larger chunks preserve more context but may exceed model limits

    **overlap** (0-500, default: 50):
    - Number of characters to overlap between consecutive chunks
    - Helps maintain context continuity across chunk boundaries
    - Only applies when chunks are created (ignored for very short texts)
    - For sentence mode: overlaps complete sentences up to the specified character count

    **split_by** ("sentence" or "char", default: "sentence"):
    - **"sentence"**: Splits at sentence boundaries (preserves semantic units)
      - Builds chunks by adding complete sentences until size limit is reached
      - More natural for reading and language processing
      - Recommended for most text analysis tasks
    - **"char"**: Splits at exact character positions
      - Precise character-based chunking regardless of sentence structure
      - Useful for strict token limit requirements
      - May break sentences mid-word

    ## Example Usage:

    ```json
    {
        "text": "Long document text here...",
        "chunk_size": 1500,
        "overlap": 100,
        "split_by": "sentence"
    }
    ```

    ```json
    {
        "text": "Precise chunking needed for token limits",
        "chunk_size": 512,
        "overlap": 0,
        "split_by": "char"
    }
    ```

    ## Response:

    Returns an array of text chunks with the specified overlap and splitting strategy applied.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="text required")

    # Validate overlap constraint
    if payload.overlap >= payload.chunk_size:
        raise HTTPException(status_code=400, detail="overlap must be less than chunk_size")

    # Clean text from potential control characters that might cause JSON issues
    try:
        # Pre-clean the text to remove any problematic characters
        cleaned_text = ''.join(char if char.isprintable() or char in '\t\n\r' else ' ' for char in payload.text)
        cleaned_text = ' '.join(cleaned_text.split())  # Normalize whitespace
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid text content: {e!s}") from e

    # Convert split_by parameter to preserve_sentences
    preserve_sentences = payload.split_by == "sentence"

    try:
        chunks = utils_core.split_text(
            cleaned_text,
            payload.chunk_size,
            overlap=payload.overlap,
            preserve_sentences=preserve_sentences
        )
        return SplitResponse(chunks=chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text splitting failed: {e!s}") from e


# --- Synonyms -------------------------------------------------------------
class SynonymRequest(BaseModel):
    """Request payload for synonym generation."""

    word: str = Field(..., min_length=1)
    max_synonyms: int = Field(5, ge=1, le=20)
    lang: str = Field("de", min_length=2, max_length=5)


class SynonymResponse(BaseModel):
    """Response containing generated synonyms."""

    synonyms: list[str]


@router.post("/synonyms", response_model=SynonymResponse)
async def synonym_endpoint(payload: SynonymRequest) -> SynonymResponse:
    """Generate synonyms for a given word using AI-powered language processing.

    This endpoint generates contextually relevant synonyms for any given word or term.
    It uses advanced language models to provide high-quality synonym suggestions.

    ## Parameters:

    **word** (required):
    - The word or term for which you want to generate synonyms
    - Can be a single word or a short phrase
    - Examples: "schnell", "Wissenschaft", "artificial intelligence"

    **max_synonyms** (1-20, default: 5):
    - Maximum number of synonyms to generate
    - Higher values provide more alternatives but may include less relevant terms

    **lang** (default: "de"):
    - Target language for synonym generation
    - Supported languages: "de" (German), "en" (English)
    - Determines the language context for synonym generation

    ## Example Usage:

    ```json
    {
        "word": "Wissenschaft",
        "max_synonyms": 8,
        "lang": "de"
    }
    ```

    ## Response:

    Returns a list of synonyms ordered by relevance and contextual appropriateness.
    """
    synonyms = utils_core.generate_synonyms(payload.word, payload.max_synonyms, lang=payload.lang)
    return SynonymResponse(synonyms=synonyms)


# --- Translate ------------------------------------------------------------
class TranslateRequest(BaseModel):
    """Request payload for text translation."""

    text: str = Field(..., min_length=1)
    target_lang: str = Field("en", min_length=2, max_length=5)


class TranslateResponse(BaseModel):
    """Response containing translated text."""

    translation: str


@router.post("/translate", response_model=TranslateResponse)
async def translate_endpoint(payload: TranslateRequest) -> TranslateResponse:
    """Translate text between different languages using AI-powered translation.

    This endpoint provides high-quality text translation using advanced language models.
    It automatically detects the source language and translates to the specified target language.

    ## Parameters:

    **text** (required):
    - The text content to be translated
    - Can be single words, phrases, sentences, or longer text passages
    - Source language is automatically detected
    - Examples: "Hallo Welt", "artificial intelligence", "Comment allez-vous?"

    **target_lang** (default: "en"):
    - The target language code for translation
    - Supported languages: "de" (German), "en" (English)
    - Determines the output language of the translation

    ## Example Usage:

    ```json
    {
        "text": "Künstliche Intelligenz revolutioniert die Wissenschaft",
        "target_lang": "en"
    }
    ```

    ```json
    {
        "text": "Machine learning algorithms are transforming healthcare",
        "target_lang": "de"
    }
    ```

    ## Response:

    Returns the translated text maintaining the original meaning and context as accurately as possible.
    """
    translation = utils_core.translate(payload.text, payload.target_lang)
    return TranslateResponse(translation=translation)
