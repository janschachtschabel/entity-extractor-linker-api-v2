"""Compendium endpoint `/compendium`.

Receives either text or entity list (output of linker) and returns markdown compendium text.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...core import compendium as comp_core

router = APIRouter(prefix="/v1", tags=["compendium"])


class InputType(str, Enum):
    """Input type for compendium generation."""

    TEXT = "text"
    LINKER_OUTPUT = "linker_output"


class CompendiumConfig(BaseModel):
    """Configuration options for compendium generation."""

    length: int = Field(default=6000, description="Target length in characters")
    enable_citations: bool = Field(default=True, description="Enable numbered citations in text")
    educational_mode: bool = Field(default=True, description="Use educational aspects for structuring")
    language: str = Field(default="de", description="Output language (de/en)")


class CompendiumRequest(BaseModel):
    """Request payload for compendium generation endpoint."""

    input_type: InputType = Field(..., description="Type of input: text or linker_output")
    text: str | None = Field(None, description="Raw text input (required if input_type=text)")
    linker_data: dict[str, Any] | None = Field(
        None,
        description=(
            "Complete JSON response from /linker endpoint - "
            "copy the entire response here when using input_type='linker_output'"
        ),
    )
    config: CompendiumConfig = Field(default_factory=CompendiumConfig, description="Compendium configuration")


class CompendiumResponse(BaseModel):
    """Response containing generated compendium content."""

    markdown: str = Field(..., description="Generated compendium in Markdown format")
    bibliography: str = Field(..., description="Numbered bibliography from Wikipedia URLs")
    statistics: dict[str, Any] = Field(..., description="Generation statistics")


@router.post("/compendium", response_model=CompendiumResponse)
def compendium_endpoint(payload: CompendiumRequest) -> CompendiumResponse:
    """Generate comprehensive markdown compendium from text or linker output.

    This endpoint creates structured, educational compendium texts in Markdown format
    with optional numbered citations and bibliography.

    ## Input Types:

    ### 1. Text Input (input_type="text")
    Direct text processing for compendium generation:
    ```json
    {
        "input_type": "text",
        "text": "Albert Einstein entwickelte die Relativitätstheorie",
        "config": {
            "length": 6000,
            "enable_citations": false,
            "educational_mode": true,
            "language": "de"
        }
    }
    ```

    ### 2. Linker Output (input_type="linker_output")
    Uses complete JSON output from /linker endpoint with entity data:
    ```json
    {
        "input_type": "linker_output",
        "linker_data": {
            "original_text": "Einstein und die Physik",
            "entities": [
                {
                    "text": "Einstein",
                    "label": "Albert Einstein",
                    "wikipedia_source": {
                        "url": "https://de.wikipedia.org/wiki/Albert_Einstein",
                        "extract": "Albert Einstein war ein deutscher Physiker..."
                    }
                }
            ]
        },
        "config": {
            "length": 8000,
            "enable_citations": true,
            "educational_mode": true,
            "language": "de"
        }
    }
    ```

    ## Configuration Options:
    - **length**: Target character count (default: 6000)
    - **enable_citations**: Include numbered citations (1), (2) in text (default: true)
    - **educational_mode**: Enhanced structured content with academic depth (default: true)
    - **language**: Output language "de" or "en" (default: "de")

    ## Response Format:
    - **markdown**: Generated compendium text in Markdown format
    - **bibliography**: Numbered bibliography from Wikipedia URLs
    - **statistics**: Generation metadata (topic, length, references count, etc.)

    ## Usage Workflow:
    1. First call `/linker` endpoint with your text
    2. Take the complete JSON response from linker
    3. Pass it as `linker_data` to this endpoint for rich compendium with citations

    Alternatively, use direct text input for simple compendium generation.
    """
    if payload.input_type == InputType.TEXT and not payload.text:
        raise HTTPException(status_code=400, detail="text required for input_type=text")

    if payload.input_type == InputType.LINKER_OUTPUT and not payload.linker_data:
        raise HTTPException(status_code=400, detail="linker_data required for input_type=linker_output")

    if payload.input_type == InputType.TEXT:
        if payload.text is None:
            raise HTTPException(status_code=400, detail="text must not be None")
        md, bibliography, statistics = comp_core.generate_compendium_from_text(str(payload.text), payload.config)
    elif payload.input_type == InputType.LINKER_OUTPUT:
        if payload.linker_data is None:
            raise HTTPException(status_code=400, detail="linker_data must not be None")
        md, bibliography, statistics = comp_core.generate_compendium(payload.linker_data, payload.config)

    return CompendiumResponse(markdown=md, bibliography=bibliography, statistics=statistics)
