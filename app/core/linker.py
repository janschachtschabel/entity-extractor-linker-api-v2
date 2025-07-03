import asyncio
from typing import Any, Literal

from loguru import logger

from app.core.openai_wrapper import extract_entities, generate_entities
from app.core.settings import settings
from app.models.entity import Entity
from app.models.entity_processing_context import EntityProcessingContext
from app.services.wikipedia import WikipediaService


async def process_text_async(
    text: str,
    mode: Literal["extract", "generate"] = "extract",
    max_entities: int = 10,
    language: Literal["de", "en"] = "de",
    educational_mode: bool = False,
    allowed_entity_types: str | list[str] = "auto",
) -> tuple[list[Entity], dict[str, Any]]:
    """
    Process text to extract entities and link them with Wikipedia data.

    Args:
        text: Input text to process
        mode: Processing mode (extract, generate)
        max_entities: Maximum number of entities to extract
        language: Target language for Wikipedia data
        educational_mode: Enable educational perspective (only for generate mode)
        allowed_entity_types: Restrict entity types (string, list, or "auto")

    Returns:
        Tuple of (entities list, statistics dict)
    """
    logger.info(
        f"Processing text with mode='{mode}', max_entities={max_entities}, "
        f"language='{language}', educational_mode={educational_mode}"
    )

    entities: list[Entity] = []
    stats: dict[str, int] = {
        "entities_extracted": 0,
        "wikipedia_pages_fetched": 0,
        "entities_linked": 0,
    }

    try:
        # Step 1: Extract or generate entities using OpenAI
        contexts = await _extract_or_generate_entities(
            text, mode, max_entities, language, educational_mode, allowed_entity_types
        )
        stats["entities_extracted"] = len(contexts)
        logger.info(f"Extracted {len(contexts)} entities")

        if not contexts:
            logger.warning("No entities extracted from text")
            return entities, stats

        # Step 2: Fetch Wikipedia data with prompt fallbacks
        logger.info(f"Fetching Wikipedia data for {len(contexts)} entities with prompt fallbacks")

        async with WikipediaService(timeout=settings.WIKIPEDIA_TIMEOUT) as wiki_service:
            # Process each entity individually with prompt metadata
            for ctx in contexts:
                # Create metadata from context for prompt fallback
                prompt_metadata = {
                    "label_de": ctx.label,  # Use extracted label as German fallback
                    "label_en": "",  # Will be filled by Wikipedia if available
                    "wiki_url_de": "",  # Will be generated if Wikipedia data found
                    "wiki_url_en": "",  # Will be generated if Wikipedia data found
                }

                # Add any existing metadata
                if hasattr(ctx, "metadata") and ctx.metadata:
                    prompt_metadata.update(ctx.metadata)

                # Process entity with fallbacks (pass language parameter)
                processed_ctx = await wiki_service.process_entity(
                    EntityProcessingContext(label=ctx.label, type=ctx.type, metadata=prompt_metadata),
                    language=language
                )

                # Update original context with Wikipedia data
                ctx.wikipedia_data = processed_ctx.wikipedia_data

                if processed_ctx.wikipedia_data and processed_ctx.wikipedia_data.get("status") in [
                    "found",
                    "found_from_prompt",
                ]:
                    stats["wikipedia_pages_fetched"] += 1
                    logger.debug(f"Successfully processed entity '{ctx.label}' with Wikipedia data")
                else:
                    logger.debug(f"No Wikipedia data found for entity '{ctx.label}'")

        # Step 3: Convert contexts to Entity objects
        for ctx in contexts:
            entity = _context_to_entity(ctx, language)
            entities.append(entity)

        stats["entities_linked"] = len([e for e in entities if e.status == "linked"])

        logger.info(f"Processing complete: {stats}")
        return entities, stats

    except Exception as e:
        logger.error(f"Error in process_text_async: {e}")
        raise


async def _extract_or_generate_entities(
    text: str,
    mode: str,
    max_entities: int,
    language: str,
    educational_mode: bool,
    allowed_entity_types: str | list[str],
) -> list[EntityProcessingContext]:
    """Extract or generate entities based on mode."""
    raw_entities: list[tuple[str, str, dict[str, Any]]] = []

    if mode == "extract":
        raw_entities = extract_entities(
            text,
            max_entities=max_entities,
            language=language,
            allowed_entity_types=allowed_entity_types,
        )
    elif mode == "generate":
        raw_entities = generate_entities(
            text,
            max_entities=max_entities,
            language=language,
            educational_mode=educational_mode,
            allowed_entity_types=allowed_entity_types,
        )
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Convert raw entities to EntityProcessingContext objects
    contexts: list[EntityProcessingContext] = []
    for label, entity_type, metadata in raw_entities:
        ctx = EntityProcessingContext(label=label, type=entity_type, metadata=metadata or {})
        contexts.append(ctx)

    logger.info(f"Converted {len(raw_entities)} raw entities to {len(contexts)} contexts")
    return contexts


def _context_to_entity(ctx: EntityProcessingContext, language: str) -> Entity:
    """
    Convert EntityProcessingContext to Entity with Wikipedia data.

    Args:
        ctx: Entity processing context
        language: Target language

    Returns:
        Entity object with Wikipedia data
    """
    # Get Wikipedia data
    wiki_data = getattr(ctx, "wikipedia_data", {}) or {}

    # Determine linking status
    has_wikipedia = wiki_data.get("status") in ["found", "found_from_prompt"]
    wikidata_id = wiki_data.get("wikidata_id", "")

    status = "linked" if (has_wikipedia and wikidata_id) else "not_linked"

    # Extract Wikipedia URLs - use correct field names
    wiki_url_de = wiki_data.get("url_de") if has_wikipedia else None
    wiki_url_en = wiki_data.get("url_en") if has_wikipedia else None

    # Extract abstracts - use language-specific abstracts
    if language == "en":
        abstract_en = wiki_data.get("extract", "") if has_wikipedia else None
        abstract_de = None  # Primary language is English
    else:
        abstract_de = wiki_data.get("extract", "") if has_wikipedia else None
        abstract_en = None  # Primary language is German

    # Extract other data
    categories = wiki_data.get("categories", []) if has_wikipedia else []
    image_url = wiki_data.get("thumbnail_url") if has_wikipedia else None
    internal_links = wiki_data.get("internal_links", []) if has_wikipedia else []
    infobox_type = wiki_data.get("infobox_type") if has_wikipedia else None

    # Extract labels (German and English) - use correct field names
    label_en = wiki_data.get("label_en", "") if has_wikipedia else None

    # Extract coordinates - use correct field names
    lat = wiki_data.get("geo_lat") if has_wikipedia else None
    lon = wiki_data.get("geo_lon") if has_wikipedia else None

    # Extract DBpedia URI
    dbpedia_uri = wiki_data.get("dbpedia_uri") if has_wikipedia else None

    return Entity(
        label=ctx.label,
        label_en=label_en,
        type=ctx.type,
        wiki_url_de=wiki_url_de,
        wiki_url_en=wiki_url_en,
        abstract_de=abstract_de,
        abstract_en=abstract_en,
        categories=categories,
        wikidata_id=wikidata_id,
        image_url=image_url,
        geo_lat=lat,
        geo_lon=lon,
        status=status,
        internal_links=internal_links,
        infobox_type=infobox_type,
        dbpedia_uri=dbpedia_uri,
    )


def _fallback_entity_extraction(text: str, max_entities: int) -> list[EntityProcessingContext]:
    """Fallback entity extraction when OpenAI is unavailable."""
    logger.warning("Using fallback entity extraction")

    # Simple named entity recognition fallback
    import re

    # Basic patterns for German entities
    patterns = [
        (r"\b[A-ZÄÖÜ][a-zäöüß]+ [A-ZÄÖÜ][a-zäöüß]+\b", "PERSON"),  # Names
        (r"\b[A-ZÄÖÜ][a-zäöüß]+(?:stadt|berg|burg|dorf|heim)\b", "LOCATION"),  # Places
        (r"\b(?:Deutschland|Österreich|Schweiz|Berlin|München|Hamburg)\b", "LOCATION"),  # Known places
    ]

    entities: list[EntityProcessingContext] = []
    for pattern, entity_type in patterns:
        matches = re.findall(pattern, text)
        for match in matches[:max_entities]:
            if len(entities) >= max_entities:
                break
            entities.append(EntityProcessingContext(label=match, type=entity_type))

    return entities[:max_entities]


def process_text(
    text: str,
    mode: Literal["extract", "generate"] = "extract",
    max_entities: int = 10,
    language: Literal["de", "en"] = "de",
    educational_mode: bool = False,
    allowed_entity_types: str | list[str] = "auto",
) -> tuple[list[Entity], dict[str, Any]]:
    """Process text synchronously using async wrapper."""
    return asyncio.run(process_text_async(text, mode, max_entities, language, educational_mode, allowed_entity_types))
