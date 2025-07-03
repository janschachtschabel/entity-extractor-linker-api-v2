"""Orchestrator endpoint that chains Linker → Compendium → QA in one call."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
import httpx
from pydantic import BaseModel, Field

from app.models.qa_base import QABaseRequest

router = APIRouter(prefix="/v1", tags=["pipeline"])


class LinkerConfig(BaseModel):
    """Configuration for the linker step."""

    MODE: Literal["extract", "generate"] = "generate"
    MAX_ENTITIES: int = Field(10, ge=1, le=100)
    ALLOWED_ENTITY_TYPES: str | list[str] | Literal["auto"] = "auto"
    EDUCATIONAL_MODE: bool = False
    LANGUAGE: Literal["de", "en"] = "de"


class CompendiumConfig(BaseModel):
    """Configuration for the compendium step."""

    length: int = Field(6000, ge=1000, le=20000)
    enable_citations: bool = True
    educational_mode: bool = True
    language: Literal["de", "en"] = "de"


class QAConfig(QABaseRequest):
    """Configuration for the QA step."""

    pass


class PipelineConfig(BaseModel):
    """Combined configuration for all pipeline steps."""

    linker: LinkerConfig = Field(default_factory=lambda: LinkerConfig(
        MODE="generate",
        MAX_ENTITIES=10,
        ALLOWED_ENTITY_TYPES="auto",
        EDUCATIONAL_MODE=False,
        LANGUAGE="de",
    ))
    compendium: CompendiumConfig = Field(default_factory=lambda: CompendiumConfig(
        length=6000,
        enable_citations=True,
        educational_mode=True,
        language="de",
    ))
    qa: QAConfig = Field(default_factory=lambda: QAConfig(
        num_pairs=10,
        max_answer_length=300,
        level_property=None,
        level_values=None,
    ))


class PipelineRequest(QABaseRequest):
    """Request for the complete pipeline."""

    text: str = Field(..., min_length=1, description="Input text to process through the complete pipeline")
    config: PipelineConfig = Field(default_factory=PipelineConfig)


class PipelineResponse(BaseModel):
    """Response containing outputs from all pipeline steps."""

    original_text: str
    linker_output: dict[str, Any]
    compendium_output: dict[str, Any]
    qa_output: dict[str, Any]
    pipeline_statistics: dict[str, Any]


@router.post("/pipeline", response_model=PipelineResponse)
async def pipeline_endpoint(payload: PipelineRequest) -> PipelineResponse:
    """Run complete educational content pipeline: Linker → Compendium → QA with Educational Levels.

    This orchestrator endpoint chains all three main endpoints with full support for
    educational level distribution and German/English educational standards:

    1. **Linker**: Extracts/generates entities with educational context
    2. **Compendium**: Generates comprehensive educational markdown content
    3. **QA**: Creates question-answer pairs distributed across
       educational levels

    ## Pipeline Flow:
    ```
    Input Text → Linker (Educational Entities) → Compendium (Educational Content) →
    QA (Level-Distributed) → Complete Output
    ```

    ## Educational Features:
    - **Educational Entity Generation**: Comprehensive coverage of educational aspects
    - **Level-Appropriate Content**: Content adapted to specified educational levels
    - **QA Level Distribution**: Even distribution across German Bildungsstufen or Bloom's Taxonomy
    - **Multi-Language Support**: German and English educational standards

    ## Configuration Options:

    ### Linker Configuration:
    - `MODE`: "extract" or "generate" (default: "generate")
    - `MAX_ENTITIES`: Maximum entities to process (default: 15)
    - `EDUCATIONAL_MODE`: Enable educational entity generation (default: true)
    - `ALLOWED_ENTITY_TYPES`: Filter entity types (optional)
    - `LANGUAGE`: Content language "de" or "en" (default: "de")

    ### Compendium Configuration:
    - `length`: Target content length in characters (default: 8000)
    - `enable_citations`: Include Wikipedia citations (default: true)
    - `educational_mode`: Educational content generation (default: true)
    - `language`: Content language "de" or "en" (default: "de")

    ### QA Configuration:
    - `num_pairs`: Number of QA pairs (default: 12)
    - `max_answer_length`: Maximum answer length (default: 300)
    - `level_property`: Educational level property name (optional)
    - `level_values`: List of educational levels (optional)

    ## Educational Level Support:

    ### German Bildungsstufen (Default):
    - Elementarbereich, Primarstufe, Sekundarstufe I, Sekundarstufe II
    - Hochschule, Berufliche Bildung, Erwachsenenbildung, Förderschule

    ### Bloom's Taxonomy:
    - Erinnern, Verstehen, Anwenden, Analysieren, Bewerten, Erschaffen

    ### Custom Taxonomies:
    - Any custom educational categories can be specified

    ## Response Structure:
    - `original_text`: Input text
    - `linker_output`: Complete entity extraction/generation results
    - `compendium_output`: Educational markdown content with citations
    - `qa_output`: QA pairs with educational level metadata
    - `pipeline_statistics`: Processing times and educational level distribution

    ## Example Usage:

    ### Standard Pipeline:
    ```json
    {
      "text": "Einstein und die Relativitätstheorie",
      "config": {
        "linker": {"MODE": "generate", "EDUCATIONAL_MODE": true},
        "compendium": {"length": 8000, "educational_mode": true},
        "qa": {"num_pairs": 12}
      }
    }
    ```

    ### Educational Levels Pipeline:
    ```json
    {
      "text": "Quantencomputing und KI",
      "config": {
        "qa": {
          "num_pairs": 16,
          "level_property": "Bildungsstufe",
          "level_values": ["Sekundarstufe II", "Hochschule", "Berufliche Bildung"]
        }
      }
    }
    ```

    ## Performance:
    - Typical processing time: 45-90 seconds for comprehensive content
    - Automatic timeout handling and error recovery
    - Detailed processing statistics and educational level distribution metrics
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    pipeline_stats: dict[str, Any] = {
        "processing_times": {},
        "completed_steps": 0,
        "errors": [],
        "total_steps": 3,
        "total_processing_time": 0,
    }

    try:
        # Step 1: Linker
        import time

        start_time = time.time()

        async with httpx.AsyncClient() as client:
            linker_request = {
                "text": payload.text,
                "config": {
                    "MODE": payload.config.linker.MODE,
                    "MAX_ENTITIES": payload.config.linker.MAX_ENTITIES,
                    "ALLOWED_ENTITY_TYPES": payload.config.linker.ALLOWED_ENTITY_TYPES,
                    "EDUCATIONAL_MODE": payload.config.linker.EDUCATIONAL_MODE,
                    "LANGUAGE": payload.config.linker.LANGUAGE,
                },
            }

            linker_response = await client.post(
                "http://localhost:8000/api/v1/linker", json=linker_request, timeout=60.0
            )

            if linker_response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Linker step failed: {linker_response.text}")

            linker_output = linker_response.json()
            pipeline_stats["processing_times"]["linker"] = time.time() - start_time
            pipeline_stats["completed_steps"] = 1

            # Step 2: Compendium
            start_time = time.time()

            compendium_request = {
                "input_type": "linker_output",
                "linker_data": linker_output,
                "config": {
                    "length": payload.config.compendium.length,
                    "enable_citations": payload.config.compendium.enable_citations,
                    "educational_mode": payload.config.compendium.educational_mode,
                    "language": payload.config.compendium.language,
                },
            }

            compendium_response = await client.post(
                "http://localhost:8000/api/v1/compendium", json=compendium_request, timeout=120.0
            )

            if compendium_response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Compendium step failed: {compendium_response.text}")

            compendium_output = compendium_response.json()
            pipeline_stats["processing_times"]["compendium"] = time.time() - start_time
            pipeline_stats["completed_steps"] = 2

            # Step 3: QA
            start_time = time.time()

            qa_request = {
                "text": compendium_output["markdown"],
                "num_pairs": payload.config.qa.num_pairs,
                "max_answer_length": payload.config.qa.max_answer_length,
            }

            # Füge Bildungsstufen-Parameter hinzu, falls konfiguriert
            if payload.config.qa.level_property and payload.config.qa.level_values:
                qa_request["level_property"] = payload.config.qa.level_property
                qa_request["level_values"] = payload.config.qa.level_values

            qa_response = await client.post("http://localhost:8000/api/v1/qa", json=qa_request, timeout=60.0)

            if qa_response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"QA step failed: {qa_response.text}")

            qa_output = qa_response.json()
            pipeline_stats["processing_times"]["qa"] = time.time() - start_time
            pipeline_stats["completed_steps"] = 3

            # Calculate total processing time
            pipeline_stats["total_processing_time"] = sum(pipeline_stats["processing_times"].values())

            return PipelineResponse(
                original_text=payload.text,
                linker_output=linker_output,
                compendium_output=compendium_output,
                qa_output=qa_output,
                pipeline_statistics=pipeline_stats,
            )

    except httpx.RequestError as e:
        pipeline_stats["errors"].append(f"Network error: {e!s}")
        raise HTTPException(status_code=503, detail=f"Pipeline communication error: {e!s}") from e
    except Exception as e:
        pipeline_stats["errors"].append(f"Unexpected error: {e!s}")
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {e!s}") from e
