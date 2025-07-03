"""Linker endpoint (placeholder).

Implements `/linker` POST endpoint. For now returns mock response.
Will integrate OpenAI-based entity extractor/generator and Wikipedia linking.
"""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1", tags=["linker"])


class LinkerConfig(BaseModel):
    """Configuration for entity linking operations."""

    MODE: Literal["extract", "generate"] = Field(default="extract", description="Processing mode for entity extraction")
    MAX_ENTITIES: int = Field(10, ge=1, le=100)
    ALLOWED_ENTITY_TYPES: str | list[str] | Literal["auto"] = "auto"
    EDUCATIONAL_MODE: bool = False
    LANGUAGE: Literal["de", "en"] = "de"


class LinkerRequest(BaseModel):
    """Request payload for entity linking endpoint."""

    text: str
    config: LinkerConfig = Field(
        default_factory=lambda: LinkerConfig(
            MODE="generate",
            MAX_ENTITIES=10,
            ALLOWED_ENTITY_TYPES="auto",
            EDUCATIONAL_MODE=False,
            LANGUAGE="de"
        )
    )


class Entity(BaseModel):
    """Represents a linked entity with metadata."""

    label: str
    type: str
    confidence: float
    wiki_url_de: str | None = None
    wiki_url_en: str | None = None
    abstract_de: str | None = None
    abstract_en: str | None = None
    wikidata_id: str | None = None
    label_en: str | None = None
    image_url: str | None = None
    categories: list[str] | None = None
    geo_lat: float | None = None
    geo_lon: float | None = None
    status: str = "not_linked"


class EntityDetails(BaseModel):
    """Entity details with type and citation information."""

    typ: str
    citation: str


class WikipediaSource(BaseModel):
    """Wikipedia source information with multilingual support."""

    status: str | None = None  # Status: found, not_found, error
    label_de: str | None = None  # Deutsches Label
    label_en: str | None = None  # Englisches Label
    url_de: str | None = None  # Deutsche URL
    url_en: str | None = None  # Englische URL
    extract: str | None = None  # Abstract (nur eine Sprache)
    categories: list[str] | None = None
    internal_links: list[str] | None = None
    wikidata_id: str | None = None
    thumbnail_url: str | None = None
    geo_lat: float | None = None
    geo_lon: float | None = None
    infobox_type: str | None = None
    dbpedia_uri: str | None = None  # DBpedia URI derived from English Wikipedia URL
    source: str = "api"
    needs_fallback: bool = False
    fallback_attempts: int = 0


class EntitySources(BaseModel):
    """Collection of entity sources from different providers."""

    wikipedia: WikipediaSource | None = None


class EnhancedEntity(BaseModel):
    """Enhanced entity with details and source information."""

    entity: str
    details: EntityDetails
    sources: EntitySources
    id: str



class Statistics(BaseModel):
    """Processing statistics for entity linking results."""

    total_entities: int
    total_relationships: int = 0
    top10: dict[str, dict[str, int]] = Field(default_factory=lambda: {
        "wikipedia_categories": dict[str, int](),
        "wikipedia_internal_links": dict[str, int](),
        "wikidata_instance_of": dict[str, int](),
        "wikidata_type": dict[str, int](),
        "wikidata_subclass_of": dict[str, int](),
        "wikidata_part_of": dict[str, int](),
        "wikidata_has_part": dict[str, int](),
        "predicates": dict[str, int](),
    })
    types_distribution: dict[str, int] = Field(default_factory=dict)
    linked: dict[str, dict[str, int | float]] = Field(
        default_factory=lambda: {"wikipedia": {"count": 0, "percent": 0.0}, "wikidata": {"count": 0, "percent": 0.0}}
    )
    relationships: dict[str, dict[str, int]] = Field(default_factory=dict)
    qa_pairs: dict[str, dict[str, int]] = Field(default_factory=dict)


class LinkerResponse(BaseModel):
    """Complete response from entity linking process."""

    original_text: str
    entities: list[EnhancedEntity]
    relationships: list[dict[str, Any]] = []
    qa_pairs: list[dict[str, Any]] = []
    statistics: Statistics


@router.post("/linker", response_model=LinkerResponse)
async def linker_endpoint(payload: LinkerRequest) -> LinkerResponse:
    """Extract or generate entities from text and link them to Wikipedia.

    This endpoint processes text to identify named entities and enriches them with Wikipedia data.

    ## Processing Modes:

    **Extract Mode** (`MODE: "extract"`):
    - Extracts entities that are explicitly mentioned in the input text
    - Identifies persons, locations, organizations, concepts, etc. from the given text
    - Best for analyzing existing content and finding referenced entities

    **Generate Mode** (`MODE: "generate"`):
    - Generates related entities that help understand the topic, even if not explicitly mentioned
    - Creates a comprehensive knowledge map around the input topic
    - Ideal for educational content creation and topic exploration

    ## Configuration Options:

    **MAX_ENTITIES** (1-100, default: 10):
    - Controls the maximum number of entities to extract/generate
    - Higher values provide more comprehensive coverage but may include less relevant entities

    **ALLOWED_ENTITY_TYPES** (string, list, or "auto"):
    - Restricts entity extraction to specific types (e.g., "PERSON", "LOCATION", "ORGANIZATION", "CONCEPT")
    - Can be a single type string, list of types, or "auto" for automatic type selection
    - Examples: "PERSON", ["PERSON", "LOCATION"], "auto"

    **EDUCATIONAL_MODE** (boolean, default: false):
    - **Only available with generate mode**
    - Enables multi-perspective educational entity generation
    - Covers comprehensive aspects: terminology, systematics, historical development,
      actors/institutions, professions, sources, educational frameworks, legal aspects,
      sustainability, interdisciplinarity, current research, and practical examples
    - Ideal for creating educational content and comprehensive topic coverage

    **LANGUAGE** ("de" or "en", default: "de"):
    - Determines the primary language for Wikipedia data retrieval
    - Affects the language of abstracts and preferred Wikipedia language versions
    - Both German and English labels/URLs are provided when available

    ## Response Structure:

    Returns enhanced entities with:
    - Wikipedia metadata (labels, URLs, abstracts, categories, coordinates)
    - Wikidata IDs for semantic linking
    - DBpedia URIs automatically generated from English Wikipedia titles
    - Entity types and confidence scores
    - Comprehensive statistics about the extraction/generation process

    ## Example Usage:

    ```json
    {
        "text": "Quantenphysik und ihre Anwendungen",
        "config": {
            "MODE": "generate",
            "MAX_ENTITIES": 15,
            "ALLOWED_ENTITY_TYPES": ["PERSON", "CONCEPT", "ORGANIZATION"],
            "EDUCATIONAL_MODE": true,
            "LANGUAGE": "de"
        }
    }
    ```
    """
    from collections import Counter
    import uuid

    from loguru import logger
    # Logging via loguru (see plan.md)

    logger.info(f"Linker-Request erhalten (Text, Länge {len(payload.text)}): {payload.text[:100]}…")
    logger.info(f"Linker-Konfiguration: {payload.config}")

    if not payload.text:
        raise HTTPException(status_code=400, detail="text is required")

    # Validate educational_mode only works with generate mode
    if payload.config.EDUCATIONAL_MODE and payload.config.MODE != "generate":
        raise HTTPException(status_code=400, detail="educational_mode can only be used with mode='generate'")

    from ...core import linker as linker_core  # relative import to avoid path issues

    logger.info("Starte Entity-Verarbeitung im Linker-Endpunkt…")
    try:
        # Call the core linker with all parameters
        entities, stats = await linker_core.process_text_async(
            text=payload.text,
            mode=payload.config.MODE,
            max_entities=payload.config.MAX_ENTITIES,
            language=payload.config.LANGUAGE,
            educational_mode=payload.config.EDUCATIONAL_MODE,
            allowed_entity_types=payload.config.ALLOWED_ENTITY_TYPES,
        )
        logger.info(f"Successfully processed {len(entities)} entities")

        # Log first few entities for debugging
        for i, entity in enumerate(entities[:3]):
            logger.debug(f"Entity {i + 1}: {entity.label} (type: {entity.type})")
            logger.debug(f"  wiki_url_de: {entity.wiki_url_de}")
            logger.debug(f"  wiki_url_en: {entity.wiki_url_en}")

        # Convert entities to enhanced format
        enhanced_entities: list[EnhancedEntity] = []
        types_distribution: Counter[str] = Counter()
        wiki_categories_counter: Counter[str] = Counter()
        wiki_internal_links_counter: Counter[str] = Counter()  # Add Counter for internal links
        linked_wikipedia_count = 0
        linked_wikidata_count = 0

        for entity in entities:
            # Count types
            types_distribution[entity.type] += 1

            # Create entity ID
            entity_id = str(uuid.uuid4())

            # Create EntityDetails
            details = EntityDetails(
                typ=entity.type,
                citation=entity.label,
            )

            # Create WikipediaSource
            # Determine status based on available data
            wiki_status = "not_found"  # Default
            if entity.wiki_url_de or entity.wiki_url_en or entity.wikidata_id:
                wiki_status = "found"

            wiki_source = WikipediaSource(
                status=wiki_status,
                label_de=entity.label,
                label_en=entity.label_en,
                url_de=entity.wiki_url_de,
                url_en=entity.wiki_url_en,
                extract=entity.abstract_de or entity.abstract_en,
                categories=entity.categories,
                internal_links=getattr(entity, "internal_links", []),
                wikidata_id=entity.wikidata_id,
                thumbnail_url=entity.image_url,
                geo_lat=entity.geo_lat,
                geo_lon=entity.geo_lon,
                infobox_type=getattr(entity, "infobox_type", None),
                dbpedia_uri=getattr(entity, "dbpedia_uri", None),
                source="api",
                needs_fallback=False,
                fallback_attempts=0,
            )

            # Count categories for statistics
            if entity.categories:
                for cat in entity.categories:
                    wiki_categories_counter[cat] += 1

            # Track linked entities
            if wiki_source.url_de or wiki_source.url_en:
                linked_wikipedia_count += 1
            if entity.wikidata_id:
                linked_wikidata_count += 1

            # Create EntitySources
            sources = EntitySources(wikipedia=wiki_source)

            # Create EnhancedEntity
            enhanced_entity = EnhancedEntity(entity=entity.label, details=details, sources=sources, id=entity_id)

            enhanced_entities.append(enhanced_entity)

        # Calculate statistics
        total_entities = len(enhanced_entities)

        # Calculate percentages
        wiki_percent = (linked_wikipedia_count / total_entities * 100) if total_entities > 0 else 0
        wikidata_percent = (linked_wikidata_count / total_entities * 100) if total_entities > 0 else 0

        # Create Statistics object
        statistics = Statistics(
            total_entities=total_entities,
            top10={
                "wikipedia_categories": dict(wiki_categories_counter.most_common(10)),
                "wikipedia_internal_links": dict(wiki_internal_links_counter.most_common(10)),
            },
            types_distribution=dict(types_distribution),
            linked={
                "wikipedia": {"count": linked_wikipedia_count, "percent": wiki_percent},
                "wikidata": {"count": linked_wikidata_count, "percent": wikidata_percent},
            },
        )

        return LinkerResponse(original_text=payload.text, entities=enhanced_entities, statistics=statistics)
    except Exception as e:
        logger.error(f"Fehler im Linker-Endpunkt: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
