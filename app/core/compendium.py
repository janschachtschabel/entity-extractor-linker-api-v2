"""Core logic for `/compendium` endpoint.

Takes either text or the output of the linker and returns a comprehensive Markdown compendium text
with numbered bibliography. Integrates with OpenAI for content generation.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from .compendium_prompts import (
    get_system_prompt_compendium_de,
    get_system_prompt_compendium_en,
    get_system_prompt_summary_de,
    get_system_prompt_summary_en,
)
from .settings import settings

try:
    import openai
except ImportError as exc:  # pragma: no cover - handled at runtime
    openai = None  # type: ignore
    logger.warning("openai package not installed: %s", exc)

MODEL_NAME: str = settings.OPENAI_MODEL


def extract_topic_from_text(text: str) -> str:
    """Extract main topic from text for compendium generation."""
    # Simple heuristic: take first meaningful sentence or first 100 characters
    sentences = text.split(".")
    if sentences and len(sentences[0].strip()) > 10:
        return sentences[0].strip()
    return text[:100].strip() if len(text) > 100 else text.strip()


def extract_topic_from_linker_data(linker_data: dict[str, Any]) -> str:
    """Extract main topic from linker output data."""
    # Use original text if available
    original_text = linker_data.get("original_text", "")
    if original_text:
        return str(extract_topic_from_text(original_text))

    # Fallback: use most prominent entity
    entities = linker_data.get("entities", [])
    if entities:
        return str(entities[0].get("entity", "Unbekanntes Thema"))

    return "Unbekanntes Thema"


def extract_references_from_linker_data(linker_data: dict[str, Any]) -> list[str]:
    """Extract Wikipedia URLs from linker data to create numbered bibliography."""
    references = []
    entities = linker_data.get("entities", [])

    for entity in entities:
        sources = entity.get("sources", {})
        wikipedia = sources.get("wikipedia", {})

        # Prefer German URL, fallback to English
        url_de = wikipedia.get("url_de")
        url_en = wikipedia.get("url_en")

        if url_de:
            references.append(url_de)
        elif url_en:
            references.append(url_en)

    # Remove duplicates while preserving order
    seen = set()
    unique_refs = []
    for ref in references:
        if ref not in seen:
            seen.add(ref)
            unique_refs.append(ref)

    return unique_refs


def create_entity_context(linker_data: dict[str, Any]) -> str:
    """Create context text from entity extracts for compendium generation."""
    context_parts = []
    entities = linker_data.get("entities", [])

    for entity in entities:
        entity_name = entity.get("entity", "")
        sources = entity.get("sources", {})
        wikipedia = sources.get("wikipedia", {})
        extract = wikipedia.get("extract", "")

        if entity_name and extract:
            context_parts.append(f"**{entity_name}**: {extract}")

    return "\n\n".join(context_parts)


def create_bibliography(references: list[str]) -> str:
    """Create numbered bibliography from references."""
    if not references:
        return "## Literaturverzeichnis\n\n*Keine Referenzen verfügbar.*"

    bib_lines = ["## Literaturverzeichnis", ""]
    for i, ref in enumerate(references, 1):
        bib_lines.append(f"{i}. {ref}")

    return "\n".join(bib_lines)


def _ensure_ready() -> None:
    """Raise RuntimeError if the OpenAI client cannot be used."""
    if openai is None:
        raise RuntimeError("OpenAI package not installed")
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not configured")


def generate_compendium_with_openai(topic: str, context: str, references: list[str], config: Any) -> str:
    """Generate compendium using OpenAI."""
    try:
        _ensure_ready()

        # Choose appropriate prompt based on language and educational mode
        if config.language == "de":
            if config.educational_mode:
                system_prompt = get_system_prompt_compendium_de(
                    topic, config.length, references, educational=True, enable_citations=config.enable_citations
                )
            else:
                system_prompt = get_system_prompt_summary_de(topic, config.length, references)
        else:
            if config.educational_mode:
                system_prompt = get_system_prompt_compendium_en(
                    topic, config.length, references, educational=True, enable_citations=config.enable_citations
                )
            else:
                system_prompt = get_system_prompt_summary_en(topic, config.length, references)

        # Prepare user message with context
        user_message = f"Thema: {topic}\n\nKontext:\n{context}" if context else f"Thema: {topic}"

        logger.debug(f"Generating compendium for topic: {topic}")
        logger.debug(f"System prompt length: {len(system_prompt)}")
        logger.debug(f"User message length: {len(user_message)}")

        response = openai.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
            temperature=0.7,
            max_tokens=4000,
            timeout=settings.OPENAI_TIMEOUT,
        )

        content = response.choices[0].message.content
        if content is None:
            return "# Fehler: Keine Antwort von OpenAI erhalten."
        return content.strip()

    except Exception as e:
        logger.error(f"Error generating compendium with OpenAI: {e}")
        return f"# Fehler bei der Generierung\n\nEs ist ein Fehler aufgetreten: {e!s}"


def generate_compendium_from_text(text: str, config: Any) -> tuple[str, str, dict[str, Any]]:
    """Generate compendium from raw text input."""
    topic = extract_topic_from_text(text)

    # For text input, we don't have Wikipedia references
    references: list[str] = []
    context = text

    # Generate compendium
    markdown = generate_compendium_with_openai(topic, context, references, config)
    bibliography = create_bibliography(references)

    statistics = {
        "topic": topic,
        "input_type": "text",
        "input_length": len(text),
        "output_length": len(markdown),
        "references_count": len(references),
        "educational_mode": config.educational_mode,
        "citations_enabled": config.enable_citations,
    }

    return markdown, bibliography, statistics


def generate_compendium(linker_data: dict[str, Any], config: Any) -> tuple[str, str, dict[str, Any]]:
    """Generate compendium from linker output data."""
    topic = extract_topic_from_linker_data(linker_data)
    references = extract_references_from_linker_data(linker_data)
    context = create_entity_context(linker_data)

    # Add original text to context if available
    original_text = linker_data.get("original_text", "")
    if original_text:
        context = f"Originaltext: {original_text}\n\nEntity-Informationen:\n{context}"

    # Generate compendium
    markdown = generate_compendium_with_openai(topic, context, references, config)
    bibliography = create_bibliography(references)

    statistics = {
        "topic": topic,
        "input_type": "linker_output",
        "entities_count": len(linker_data.get("entities", [])),
        "output_length": len(markdown),
        "references_count": len(references),
        "educational_mode": config.educational_mode,
        "citations_enabled": config.enable_citations,
    }

    return markdown, bibliography, statistics


# Legacy function for backward compatibility
def generate_compendium_legacy(entities: list[dict[str, Any]]) -> str:
    """Generate a markdown compendium based on *entities* (legacy version)."""
    if not entities:
        return "*Keine Entitäten gefunden.*"

    md_lines: list[str] = ["## Kompendium", ""]

    for ent in entities:
        label = ent.get("label")
        wiki_de = ent.get("wiki_url_de")
        wiki_en = ent.get("wiki_url_en")
        md_line = f"* **{label}** - [DE]({wiki_de}) | [EN]({wiki_en})"
        md_lines.append(md_line)

    md_lines.append("\n## Referenzen\n")
    for ent in entities:
        if ent.get("wiki_url_en"):
            md_lines.append(f"- {ent['wiki_url_en']}")
        if ent.get("wiki_url_de"):
            md_lines.append(f"- {ent['wiki_url_de']}")

    return "\n".join(md_lines)
