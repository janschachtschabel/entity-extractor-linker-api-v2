"""OpenAI helper functions.

Wraps OpenAI ChatCompletion calls and provides minimal helpers used by the
utility endpoints (translation, synonym generation, entity extraction). All
requests use the configurable timeout from `settings.OPENAI_TIMEOUT`.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .settings import settings

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    openai_available = True
except ImportError as exc:  # pragma: no cover - handled at runtime
    OpenAI = None  # type: ignore
    openai_available = False
    logger.warning("openai package not installed: %s", exc)

MODEL_NAME: str = settings.OPENAI_MODEL

# Global OpenAI client instance
openai = None
if openai_available and getattr(settings, "OPENAI_BASE_URL", None):
    openai = OpenAI(api_key=settings.OPENAI_API_KEY)
    if settings.OPENAI_BASE_URL:
        openai.base_url = str(settings.OPENAI_BASE_URL)

# ---------------------------------------------------------------------------
# Educational Mode Helpers
# ---------------------------------------------------------------------------


def get_educational_block_de() -> str:
    """Return German educational mode prompt block."""
    return (
        "Ergänzen Sie die Entitäten so, dass sie das für Bildungszwecke relevante Weltwissen zum Thema abbilden. "
        "Nutzen Sie folgende Aspekte zur Strukturierung: Einführung, Zielsetzung, Grundlegendes – Thema, Zweck, "
        "Abgrenzung, Beitrag zum Weltwissen; Grundlegende Fachinhalte & Terminologie (inkl. Englisch) – "
        "Schlüsselbegriffe, Formeln, Gesetzmäßigkeiten, mehrsprachiges Fachvokabular; Systematik & Untergliederung "
        "– Fachliche Struktur, Teilgebiete, Klassifikationssysteme; Gesellschaftlicher Kontext – Alltag, Haushalt, "
        "Natur, Hobbys, soziale Themen, öffentliche Debatten; Historische Entwicklung – Zentrale Meilensteine, "
        "Personen, Orte, kulturelle Besonderheiten; Akteure, Institutionen & Netzwerke – Wichtige Persönlichkeiten "
        "(historisch & aktuell), Organisationen, Projekte; Beruf & Praxis – Relevante Berufe, Branchen, Kompetenzen, "
        "kommerzielle Nutzung; Quellen, Literatur & Datensammlungen – Standardwerke, Zeitschriften, Studien, "
        "OER-Repositorien, Datenbanken; Bildungspolitische & didaktische Aspekte – Lehrpläne, Bildungsstandards, "
        "Lernorte, Lernmaterialien, Kompetenzrahmen; Rechtliche & ethische Rahmenbedingungen – Gesetze, Richtlinien, "
        "Lizenzmodelle, Datenschutz, ethische Grundsätze; Nachhaltigkeit & gesellschaftliche Verantwortung – "
        "Ökologische und soziale Auswirkungen, globale Ziele, Technikfolgenabschätzung; Interdisziplinarität & "
        "Anschlusswissen – Fachübergreifende Verknüpfungen, mögliche Synergien, angrenzende Wissensgebiete; "
        "Aktuelle Entwicklungen & Forschung – Neueste Studien, Innovationen, offene Fragen, Zukunftstrends; "
        "Verknüpfung mit anderen Ressourcentypen – Personen, Orte, Organisationen, Berufe, technische Tools, "
        "Metadaten; Praxisbeispiele, Fallstudien & Best Practices – Konkrete Anwendungen, Transfermodelle, "
        "Checklisten, exemplarische Projekte."
    )


def get_educational_block_en() -> str:
    """Return English educational mode prompt block."""
    return (
        "If educational mode is enabled, generate entities representing world knowledge relevant for educational "
        "purposes about the topic. "
        "Structure them using the following aspects: Introduction, Objectives, Fundamentals – topic, purpose, scope, "
        "contribution to world knowledge; Fundamental Concepts & Terminology (including English terms) – key terms, "
        "formulas, laws, multilingual technical vocabulary; Systematics & Structure – domain structure, subfields, "
        "classification systems; Societal Context – everyday life, household, nature, hobbies, social issues, "
        "public debates; Historical Development – key milestones, persons, places, cultural particularities; "
        "Actors, Institutions & Networks – important personalities (historical & current), organizations, projects; "
        "Professions & Practice – relevant professions, industries, competencies, commercial applications; "
        "Sources, Literature & Data Collections – standard works, journals, studies, OER repositories, databases; "
        "Educational & Didactic Aspects – curricula, educational standards, learning environments, learning materials, "
        "competency frameworks; Legal & Ethical Frameworks – laws, guidelines, licensing models, data protection, "
        "ethical principles; Sustainability & Social Responsibility – ecological and social impacts, global goals, "
        "technology assessment; Interdisciplinarity & Further Knowledge – cross-disciplinary connections, potential "
        "synergies, adjacent fields; Current Developments & Research – latest studies, innovations, open questions, "
        "future trends; Linking with Other Resource Types – people, places, organizations, professions, technical "
        "tools, metadata; Practical Examples, Case Studies & Best Practices – concrete applications, transfer models, "
        "checklists, exemplary projects."
    )


def _format_allowed_entity_types(allowed_entity_types: str | list[str] | None) -> str:
    """Format allowed entity types for prompt inclusion."""
    if allowed_entity_types == "auto" or not allowed_entity_types:
        return "Focus on the most relevant entity types (PERSON, LOCATION, ORGANIZATION, CONCEPT, etc.)."

    if isinstance(allowed_entity_types, str):
        types_list = [allowed_entity_types]
    else:
        types_list = list(allowed_entity_types)

    types_str = ", ".join(types_list)
    return f"IMPORTANT: Only extract/generate entities of these types: {types_str}. Ignore all other entity types."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_ready() -> None:
    """Raise RuntimeError if the OpenAI client cannot be used."""
    global openai
    if not openai_available:
        raise RuntimeError("openai package not installed")
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in environment")
    if openai is None:
        openai = OpenAI(api_key=settings.OPENAI_API_KEY)


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------


def translate_text(
    text: str,
    *,
    target_lang: str = "en",
    source_lang: str | None = None,
) -> str:
    """Translate *text* to *target_lang* using ChatCompletion."""
    _ensure_ready()

    system_prompt = (
        "You are a translation engine. Translate the user text into "
        f"{target_lang.upper()}. Do not add explanations, only the translated text."
    )
    if source_lang:
        system_prompt += f"\nSource language is {source_lang.upper()}."

    logger.debug("Calling OpenAI for translation (→%s)", target_lang)
    assert openai is not None  # ensured by _ensure_ready()
    response = openai.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0.0,
        timeout=settings.OPENAI_TIMEOUT,
        max_tokens=len(text) * 2 // 4 + 50,  # rough heuristic
    )
    content = response.choices[0].message.content
    return content.strip() if content else ""


# ---------------------------------------------------------------------------
# Synonyms
# ---------------------------------------------------------------------------


def generate_synonyms_llm(
    word: str,
    *,
    max_synonyms: int = 5,
    lang: str = "de",
) -> list[str]:
    """Return up to *max_synonyms* synonyms for *word* via ChatCompletion."""
    _ensure_ready()

    sys_prompt = (
        "You are a thesaurus assistant. For a given word, return a JSON array "
        "containing distinct synonyms in the requested language. Do not output "
        "anything except the JSON array."
    )
    user_prompt = f"LANGUAGE: {lang}\nWORD: {word}\nMAX: {max_synonyms}\nReturn synonyms now."
    logger.debug("Calling OpenAI for synonyms of '%s'", word)
    assert openai is not None  # ensured by _ensure_ready()
    response = openai.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        timeout=settings.OPENAI_TIMEOUT,
        max_tokens=100,
    )
    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("OpenAI returned empty content")
    try:
        data = json.loads(content)
        if not isinstance(data, list):
            raise ValueError("Expected JSON array")
        return [str(w) for w in data][:max_synonyms]
    except Exception as exc:  # pylint: disable=broad-except
        raise RuntimeError(f"Invalid JSON from OpenAI: {exc}") from exc


# ---------------------------------------------------------------------------
# Entity extraction / generation
# ---------------------------------------------------------------------------


def generate_entities(
    text: str,
    max_entities: int = 10,
    language: str = "de",
    educational_mode: bool = False,
    allowed_entity_types: str | list[str] | None = "auto",
) -> list[tuple[str, str, dict[str, Any]]]:
    """Generate plausible entities related to *text*.

    This is similar to :func:`extract_entities` but instructs the model to
    think about *related* concepts that might not explicitly appear in the
    text yet. The implementation is intentionally very similar to the
    extraction helper to keep the surface consistent.

    Args:
        text: Input text to analyze
        max_entities: Maximum number of entities to generate
        language: Target language (de/en)
        educational_mode: Enable educational perspective for entity generation
        allowed_entity_types: Restrict entity types (string, list, or "auto")

    Returns list of (label, TYPE, metadata) where metadata contains Wikipedia article titles.
    """
    _ensure_ready()

    # Build entity type constraint
    entity_type_instruction = _format_allowed_entity_types(allowed_entity_types)

    # Build educational mode instruction
    educational_instruction = ""
    if educational_mode:
        if language == "de":
            educational_instruction = f"\n\nBILDUNGSMODUS AKTIVIERT:\n{get_educational_block_de()}"
        else:
            educational_instruction = f"\n\nEDUCATIONAL MODE ENABLED:\n{get_educational_block_en()}"

    # Enhanced system prompt that instructs the model to generate exact Wikipedia article titles
    system_prompt = (
        f"You are an AI system for suggesting named entities relevant to the given text. "
        f"Your task is to identify up to {max_entities} important related entities "
        f"and provide their exact Wikipedia article titles.\n\n"
        f"CRITICAL: Use the EXACT Wikipedia article title format. Examples:\n"
        f"- For Goethe: 'Johann Wolfgang von Goethe' (not just 'Goethe')\n"
        f"- For Einstein: 'Albert Einstein' (not 'Einstein')\n"
        f"- For Berlin: 'Berlin' (the city)\n"
        f"- For Germany: 'Germany' (the country)\n\n"
        f"{entity_type_instruction}\n\n"
        f"For each entity, provide:\n"
        f"- label_de: The canonical German Wikipedia article title (exact format)\n"
        f"- label_en: The canonical English Wikipedia article title (exact format)\n"
        f"- type: The entity type (e.g. PERSON, LOCATION, ORGANIZATION)\n"
        f"- wikipedia_url_de: null (will be generated automatically)\n"
        f"- wikipedia_url_en: null (will be generated automatically)\n"
        f"- wikidata_id: null (will be fetched automatically)\n\n"
        f"Return a JSON array of objects with these keys. Focus on using the EXACT canonical Wikipedia article titles."
        f"{educational_instruction}"
    )
    user_prompt = (
        f"TEXT (language={language}):\n{text}\n\n"
        f"Think about related important concepts and list up to {max_entities} "
        "additional entities that would help a student understand the text. "
        "Use EXACT Wikipedia article titles for both German and English labels. Return JSON only."
    )

    logger.debug(
        "Calling OpenAI model %s for entity *generation* with Wikipedia article titles (educational_mode=%s)",
        MODEL_NAME,
        educational_mode,
    )
    logger.debug(f"[generate_entities] System prompt:\n{system_prompt}\nUser prompt:\n{user_prompt}")
    assert openai is not None  # ensured by _ensure_ready()
    response = openai.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        timeout=settings.OPENAI_TIMEOUT,
        max_tokens=800,  # Increased token limit for Wikipedia URLs
    )
    content = response.choices[0].message.content
    try:
        # Clean content - remove markdown code blocks if present
        cleaned_content = content.strip() if content else ""
        if cleaned_content.startswith("```json"):
            cleaned_content = cleaned_content[7:]  # Remove ```json
        if cleaned_content.startswith("```"):
            cleaned_content = cleaned_content[3:]   # Remove ```
        if cleaned_content.endswith("```"):
            cleaned_content = cleaned_content[:-3]  # Remove trailing ```
        cleaned_content = cleaned_content.strip()

        items = json.loads(cleaned_content)
        if isinstance(items, dict):
            items = items.get("entities", [])
        else:
            items = items

        # Log the raw response for debugging
        logger.debug(f"OpenAI generation returned {len(items)} items")

        entities = []
        for item in items:
            label_de = item.get("label_de") or item.get("label", "").strip()
            label_en = item.get("label_en")
            typ = str(item.get("type", "UNKNOWN")).upper()

            # Collect metadata including Wikipedia article titles and both labels
            metadata = {
                "label_de": label_de,
                "label_en": label_en,
                "wiki_url_de": item.get("wikipedia_url_de"),
                "wiki_url_en": item.get("wikipedia_url_en"),
                "wikidata_id": item.get("wikidata_id"),
            }

            if label_de:
                entities.append((label_de, typ, metadata))
                logger.debug(
                    f"Generated entity: {label_de} ({typ}) [EN: {label_en}] with URLs: "
                    f"DE: {metadata.get('wiki_url_de')}, EN: {metadata.get('wiki_url_en')}"
                )

        return entities
    except json.JSONDecodeError as exc:
        # Log the raw content to help debug JSON parsing issues
        content_preview = content[:200] if content else "None"
        logger.error(f"JSON parsing error in generation. Content: {content_preview}...")
        raise RuntimeError(f"Invalid JSON from OpenAI: {exc}") from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise RuntimeError(f"Error processing OpenAI response in generation: {exc}") from exc


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------


def extract_entities(
    text: str,
    max_entities: int = 10,
    language: str = "de",
    allowed_entity_types: str | list[str] | None = "auto",
) -> list[tuple[str, str, dict[str, Any]]]:
    """Extract up to *max_entities* entities from *text*.

    Args:
        text: Input text to analyze
        max_entities: Maximum number of entities to extract
        language: Target language (de/en)
        allowed_entity_types: Restrict entity types (string, list, or "auto")

    Returns list of (label, TYPE, metadata) where metadata contains Wikipedia article titles.
    """
    _ensure_ready()

    # Build entity type constraint
    entity_type_instruction = _format_allowed_entity_types(allowed_entity_types)

    # Enhanced system prompt that instructs the model to extract exact Wikipedia article titles
    system_prompt = (
        f"You are an AI system for recognizing and linking entities. "
        f"Your task is to identify up to {max_entities} important entities from the given text "
        f"and provide their exact Wikipedia article titles.\n\n"
        f"CRITICAL: Use the EXACT Wikipedia article title format. Examples:\n"
        f"- For Goethe: 'Johann Wolfgang von Goethe' (not just 'Goethe')\n"
        f"- For Einstein: 'Albert Einstein' (not 'Einstein')\n"
        f"- For Berlin: 'Berlin' (the city)\n"
        f"- For Germany: 'Germany' (the country)\n\n"
        f"{entity_type_instruction}\n\n"
        f"For each entity, provide:\n"
        f"- label_de: The canonical German Wikipedia article title (exact format)\n"
        f"- label_en: The canonical English Wikipedia article title (exact format)\n"
        f"- type: The entity type (e.g. PERSON, LOCATION, ORGANIZATION)\n"
        f"- wikipedia_url_de: null (will be generated automatically)\n"
        f"- wikipedia_url_en: null (will be generated automatically)\n"
        f"- wikidata_id: null (will be fetched automatically)\n\n"
        f"Return a JSON array of objects with these keys. Focus on using the EXACT canonical Wikipedia article titles."
    )

    user_prompt = (
        f"TEXT (language={language}):\n{text}\n\n"
        f"Extract up to {max_entities} distinct entities using EXACT Wikipedia article titles. JSON format only."
    )

    logger.debug("Calling OpenAI model %s for entity extraction with Wikipedia article titles", MODEL_NAME)
    logger.debug(f"[extract_entities] System prompt:\n{system_prompt}\nUser prompt:\n{user_prompt}")
    assert openai is not None  # ensured by _ensure_ready()
    response = openai.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        timeout=settings.OPENAI_TIMEOUT,
        max_tokens=800,  # Increased token limit for Wikipedia URLs
    )
    content = response.choices[0].message.content
    try:
        # Clean content - remove markdown code blocks if present
        cleaned_content = content.strip() if content else ""
        if cleaned_content.startswith("```json"):
            cleaned_content = cleaned_content[7:]  # Remove ```json
        if cleaned_content.startswith("```"):
            cleaned_content = cleaned_content[3:]   # Remove ```
        if cleaned_content.endswith("```"):
            cleaned_content = cleaned_content[:-3]  # Remove trailing ```
        cleaned_content = cleaned_content.strip()

        items = json.loads(cleaned_content)
        if not isinstance(items, list):
            raise ValueError("Expected JSON array")

        # Log the raw response for debugging
        logger.debug(f"OpenAI extraction returned {len(items)} items")

        entities = []
        for item in items:
            label_de = item.get("label_de") or item.get("label", "").strip()
            label_en = item.get("label_en")
            typ = str(item.get("type", "UNKNOWN")).upper()

            # Collect metadata including Wikipedia article titles and both labels
            metadata = {
                "label_de": label_de,
                "label_en": label_en,
                "wiki_url_de": item.get("wikipedia_url_de"),
                "wiki_url_en": item.get("wikipedia_url_en"),
                "wikidata_id": item.get("wikidata_id"),
            }

            if label_de:
                entities.append((label_de, typ, metadata))
                logger.debug(
                    f"Extracted entity: {label_de} ({typ}) [EN: {label_en}] with URLs: "
                    f"DE: {metadata.get('wiki_url_de')}, EN: {metadata.get('wiki_url_en')}"
                )

        return entities
    except json.JSONDecodeError as exc:
        # Log the raw content to help debug JSON parsing issues
        content_preview = content[:200] if content else "None"
        logger.error(f"JSON parsing error. Content: {content_preview}...")
        raise RuntimeError(f"Invalid JSON from OpenAI: {exc}") from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise RuntimeError(f"Error processing OpenAI response: {exc}") from exc
