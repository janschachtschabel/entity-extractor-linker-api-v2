"""Generate question/answer pairs from compendium markdown."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def generate_qa_pairs(
    markdown: str, num_pairs: int = 5, topic: str | None = None, max_chars: int | None = None
) -> list[tuple[str, str]]:
    """Return list of (question, answer) tuples.

    Parameters
    ----------
    markdown : str
        Markdown content to generate QA pairs from
    num_pairs : int, default 5
        Number of QA pairs to generate
    topic : str, optional
        Specific topic to focus questions on
    max_chars : int, optional
        Maximum character length for each answer

    Raises
    ------
    RuntimeError
        If OpenAI is not available or configured properly
    ValueError
        If OpenAI returns invalid or empty response
    """
    logger.info(f"[generate_qa_pairs] Called with num_pairs={num_pairs}, max_chars={max_chars}")

    try:
        # Einfacher Prompt für Semikolon-Format
        prompt = (
            "Du bist ein Assistent, der Lernfragen erstellt. "
            f"Erstelle basierend auf dem folgenden Text GENAU {num_pairs} verschiedene Frage-Antwort-Paare. "
            "WICHTIG: Antworte NUR mit den Frage-Antwort-Paaren im folgenden Format:\n\n"
            "Frage 1;Antwort 1\n"
            "Frage 2;Antwort 2\n"
            "Frage 3;Antwort 3\n\n"
            "Jedes Paar in eine neue Zeile, getrennt durch Semikolon. "
            "Keine zusätzlichen Erklärungen, keine Nummerierung, keine Markdown-Formatierung.\n"
            f"ANZAHL PAARE: {num_pairs}\n"
        )

        if topic:
            prompt += f"SCHWERPUNKT: {topic}\n"

        if max_chars:
            prompt += f"MAX ANTWORTLÄNGE: {max_chars} Zeichen\n"

        prompt += f"\nTEXT:\n{markdown}\n\n"
        prompt += f"Erstelle nun {num_pairs} Frage-Antwort-Paare:"

        logger.debug(f"[generate_qa_pairs] Calling OpenAI with prompt length: {len(prompt)}")

        # Call OpenAI with our enhanced prompt
        pairs = _call_openai_generate(prompt, num_pairs, max_chars)
        if pairs:
            logger.info(f"[generate_qa_pairs] OpenAI returned {len(pairs)} QA pairs")
            return pairs
        else:
            logger.error("[generate_qa_pairs] OpenAI returned empty result")
            raise ValueError("OpenAI returned empty or invalid response for QA generation")

    except Exception as exc:  # pylint: disable=broad-except
        logger.error(f"[generate_qa_pairs] OpenAI QA generation failed: {type(exc).__name__}: {exc}")
        # Re-raise the exception instead of using fallback
        if isinstance(exc, RuntimeError | ValueError):
            raise
        raise RuntimeError(f"QA generation failed: {exc}") from exc


def _call_openai_generate(prompt: str, num_pairs: int, max_chars: int | None = None) -> list[tuple[str, str]]:
    """Direct OpenAI chat call wrapped for QA generation."""
    from . import openai_wrapper  # reuse ensure_ready & openai import

    logger.debug(f"[_call_openai_generate] Starting OpenAI call for {num_pairs} pairs")

    openai_wrapper._ensure_ready()
    openai = openai_wrapper.openai

    if openai is None:
        raise RuntimeError("OpenAI-Client ist nicht initialisiert.")
    response = openai.chat.completions.create(
        model=openai_wrapper.MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,  # Etwas mehr Kreativität
        max_tokens=2000,  # Mehr Tokens für mehrere Paare
    )

    content = response.choices[0].message.content
    logger.debug(f"[_call_openai_generate] OpenAI raw response: {content}")

    try:
        # Einfache Bereinigung für Semikolon-Format
        if content is None:
            raise RuntimeError("OpenAI-Antwort enthält keinen Content.")
        cleaned_content = content.strip()
        # Entferne mögliche Code-Fences
        if cleaned_content.startswith("```"):
            lines = cleaned_content.split("\n")
            cleaned_content = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned_content

        logger.debug(f"[_call_openai_generate] Cleaned content: {cleaned_content}")

        # Semikolon-Format direkt parsen
        pairs = []
        for line in cleaned_content.splitlines():
            line = line.strip()
            if ";" in line and line:
                parts = line.split(";", 1)
                if len(parts) == 2:
                    q, a = parts
                    q = q.strip()
                    a = a.strip()

                    if q and a:  # Beide müssen vorhanden sein
                        if max_chars and len(a) > max_chars:
                            a = a[: max_chars - 3] + "..."
                        pairs.append((q, a))
                        logger.debug(f"[_call_openai_generate] Added pair: '{q}' -> '{a[:50]}...'")

        logger.info(f"[_call_openai_generate] Successfully extracted {len(pairs)} QA pairs (requested: {num_pairs})")

        # Warnung falls weniger Paare als erwartet
        if len(pairs) < num_pairs:
            logger.warning(f"[_call_openai_generate] Only got {len(pairs)} pairs instead of requested {num_pairs}")

        return pairs

    except Exception as exc:
        logger.error(f"[_call_openai_generate] Fehler beim Verarbeiten der OpenAI-Antwort: {exc}")
        return []


def generate_qa_pairs_with_levels(
    markdown: str,
    num_pairs: int = 5,
    topic: str | None = None,
    max_chars: int | None = None,
    level_property: str = "Bildungsstufe",
    level_values: list[str] | None = None
) -> list[tuple[str, str, str, str]]:
    """Return list of (question, answer, level_property, level_value) tuples.

    Parameters
    ----------
    markdown : str
        Markdown content to generate QA pairs from
    num_pairs : int, default 5
        Number of QA pairs to generate
    topic : str, optional
        Specific topic to focus questions on
    max_chars : int, optional
        Maximum character length for each answer
    level_property : str, default "Bildungsstufe"
        Name of the educational level property
    level_values : List[str], optional
        List of educational level values to distribute QA pairs across

    Raises
    ------
    RuntimeError
        If OpenAI is not available or configured properly
    ValueError
        If OpenAI returns invalid or empty response
    """
    if not level_values:
        # Deutsche Bildungssystem-Standards als Standardwerte
        level_values = [
            "Elementarbereich",
            "Primarstufe",
            "Sekundarstufe I",
            "Sekundarstufe II",
            "Hochschule",
            "Berufliche Bildung",
            "Erwachsenenbildung",
            "Förderschule"
        ]

    logger.info(
        f"[generate_qa_pairs_with_levels] Called with num_pairs={num_pairs}, "
        f"level_property='{level_property}', level_values={level_values}"
    )

    try:
        # Berechne gleichmäßige Verteilung der QA-Paare auf Bildungsstufen
        pairs_per_level = _distribute_pairs_across_levels(num_pairs, level_values)
        logger.info(f"[generate_qa_pairs_with_levels] Distribution: {pairs_per_level}")

        # Erstelle erweiterten Prompt mit Bildungsstufen-Instruktionen
        prompt = _create_educational_levels_prompt(
            markdown, num_pairs, level_property, level_values,
            pairs_per_level, topic, max_chars
        )

        logger.debug(f"[generate_qa_pairs_with_levels] Calling OpenAI with prompt length: {len(prompt)}")

        # Call OpenAI with enhanced prompt
        pairs_with_levels = _call_openai_generate_with_levels(
            prompt, num_pairs, level_property, level_values, max_chars
        )

        if pairs_with_levels:
            logger.info(
                f"[generate_qa_pairs_with_levels] OpenAI returned {len(pairs_with_levels)} QA pairs with levels"
            )
            return pairs_with_levels
        logger.error("[generate_qa_pairs_with_levels] OpenAI returned empty result")
        raise ValueError("OpenAI returned empty or invalid response for educational levels QA generation")

    except Exception as exc:
        logger.error(f"[generate_qa_pairs_with_levels] OpenAI QA generation failed: {type(exc).__name__}: {exc}")
        if isinstance(exc, RuntimeError | ValueError):
            raise
        raise RuntimeError(f"Educational levels QA generation failed: {exc}") from exc


def _distribute_pairs_across_levels(num_pairs: int, level_values: list[str]) -> dict[str, int]:
    """Distribute QA pairs evenly across educational levels."""
    base_pairs = num_pairs // len(level_values)
    extra_pairs = num_pairs % len(level_values)

    distribution = {}
    for i, level in enumerate(level_values):
        distribution[level] = base_pairs + (1 if i < extra_pairs else 0)

    return distribution


def _create_educational_levels_prompt(
    markdown: str, num_pairs: int, level_property: str, level_values: list[str],
    pairs_per_level: dict[str, int], topic: str | None = None, max_chars: int | None = None
) -> str:
    """Create enhanced prompt for educational levels QA generation."""
    prompt = (
        "Du bist ein Bildungsexperte, der Lernfragen für verschiedene Bildungsstufen erstellt. "
        f"Erstelle basierend auf dem folgenden Text GENAU {num_pairs} verschiedene Frage-Antwort-Paare "
        f"und verteile sie gleichmäßig auf die angegebenen {level_property}-Stufen.\n\n"
        "WICHTIGES FORMAT: Jede Zeile muss folgendes Format haben:\n"
        "Frage;Antwort;Bildungsstufe\n\n"
        "WICHTIGE REGELN:\n"
        "- KEINE Nummerierungen oder Aufzählungszeichen in den Fragen verwenden\n"
        "- Fragen beginnen direkt mit dem Fragewort (Was, Wie, Warum, etc.)\n"
        "- Jede Frage steht für sich und ist eigenständig formuliert\n\n"
        "VERTEILUNG DER FRAGEN:\n"
    )

    for level, count in pairs_per_level.items():
        prompt += f"- {level}: {count} Frage(n)\n"

    prompt += f"\n{level_property.upper()}-ANPASSUNG:\n"
    for level in level_values:
        # Deutsche Bildungsstufen
        if level == "Elementarbereich":
            prompt += (
                f"- {level}: Sehr einfache Sprache, spielerische Fragen, "
                f"bildhafte Erklärungen, sehr kurze Antworten\n"
            )
        elif level == "Primarstufe" or "Grundschule" in level:
            prompt += f"- {level}: Einfache Sprache, grundlegende Konzepte, anschauliche Beispiele, kurze Antworten\n"
        elif level == "Sekundarstufe I":
            prompt += f"- {level}: Altersgerechte Sprache, systematischer Aufbau, mittlere Komplexität\n"
        elif level == "Sekundarstufe II":
            prompt += f"- {level}: Differenzierte Sprache, vertiefende Inhalte, wissenschaftspropädeutisch\n"
        elif level == "Hochschule" or "Universität" in level:
            prompt += (
                f"- {level}: Fachsprache, komplexe Zusammenhänge, "
                f"wissenschaftliche Tiefe, detaillierte Antworten\n"
            )
        elif level == "Berufliche Bildung" or "Berufsbildung" in level:
            prompt += f"- {level}: Praxisbezug, anwendungsorientierte Fragen, berufsspezifische Kontexte\n"
        elif level == "Erwachsenenbildung":
            prompt += f"- {level}: Lebenserfahrung berücksichtigend, selbstgesteuert, praxisrelevant\n"
        elif level == "Förderschule":
            prompt += f"- {level}: Besonders einfache Sprache, kleinschrittig, unterstützende Erklärungen\n"
        # Bloomsche Taxonomie (falls verwendet)
        elif level in ["Erinnern", "Verstehen", "Anwenden", "Analysieren", "Bewerten", "Erschaffen"]:
            bloom_instructions = {
                "Erinnern": "Faktenwissen abrufen, einfache Wiedergabe",
                "Verstehen": "Bedeutung erfassen, eigene Worte verwenden",
                "Anwenden": "Wissen in neuen Situationen nutzen",
                "Analysieren": "Zusammenhänge erkennen, Strukturen aufdecken",
                "Bewerten": "Kritisch beurteilen, Argumente abwägen",
                "Erschaffen": "Neue Lösungen entwickeln, kreativ kombinieren"
            }
            prompt += f"- {level}: {bloom_instructions.get(level, 'Angemessene kognitive Anforderung')}\n"
        else:
            prompt += f"- {level}: Angemessene Komplexität und Sprache für diese Stufe\n"

    if topic:
        prompt += f"\nSCHWERPUNKT: {topic}\n"

    if max_chars:
        prompt += f"\nMAX ANTWORTLÄNGE: {max_chars} Zeichen\n"

    prompt += f"\nTEXT:\n{markdown}\n\n"
    prompt += f"Erstelle nun {num_pairs} Frage-Antwort-Paare mit der angegebenen Verteilung:"

    return prompt


def _call_openai_generate_with_levels(
    prompt: str, num_pairs: int, level_property: str,
    level_values: list[str], max_chars: int | None = None
) -> list[tuple[str, str, str, str]]:
    """OpenAI call for educational levels QA generation."""
    from . import openai_wrapper

    logger.debug(f"[_call_openai_generate_with_levels] Starting OpenAI call for {num_pairs} pairs with levels")

    openai_wrapper._ensure_ready()
    openai = openai_wrapper.openai

    if openai is None:
        raise RuntimeError("OpenAI-Client ist nicht initialisiert.")
    response = openai.chat.completions.create(
        model=openai_wrapper.MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=3000,  # Mehr Tokens für Bildungsstufen-Informationen
    )

    content = response.choices[0].message.content
    logger.debug(f"[_call_openai_generate_with_levels] OpenAI raw response: {content}")

    try:
        # Parse erweiterte Semikolon-Format: Frage;Antwort;Bildungsstufe
        if content is None:
            raise RuntimeError("OpenAI-Antwort enthält keinen Content.")
        cleaned_content = content.strip()
        if cleaned_content.startswith("```"):
            lines = cleaned_content.split("\n")
            cleaned_content = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned_content

        logger.debug(f"[_call_openai_generate_with_levels] Cleaned content: {cleaned_content}")

        pairs_with_levels = []
        for line in cleaned_content.splitlines():
            line = line.strip()
            if line.count(";") >= 2:  # Mindestens 2 Semikola für Frage;Antwort;Level
                parts = line.split(";", 2)  # Maximal 3 Teile
                if len(parts) >= 3:
                    q, a, level = parts[0].strip(), parts[1].strip(), parts[2].strip()

                    # Entferne Nummerierungen aus Fragen (z.B. "1. ", "2) ", "a) ")
                    q = re.sub(r'^\d+[.)\s]+', '', q).strip()
                    q = re.sub(r'^[a-zA-Z][.)\s]+', '', q).strip()

                    if q and a and level:
                        # Validiere dass die Bildungsstufe in der Liste ist
                        if level not in level_values:
                            # Versuche ähnliche Bildungsstufe zu finden
                            level = _find_closest_level(level, level_values)

                        if max_chars and len(a) > max_chars:
                            a = a[:max_chars - 3] + "..."

                        pairs_with_levels.append((q, a, level_property, level))
                        logger.debug(
                            f"[_call_openai_generate_with_levels] Added pair: '{q}' -> '{a[:50]}...' [{level}]"
                        )

        logger.info(
            f"[_call_openai_generate_with_levels] Successfully extracted {len(pairs_with_levels)} "
            f"QA pairs with levels (requested: {num_pairs})"
        )

        if len(pairs_with_levels) < num_pairs:
            logger.warning(
                f"[_call_openai_generate_with_levels] Only got {len(pairs_with_levels)} "
                f"pairs instead of requested {num_pairs}"
            )

        return pairs_with_levels

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"[_call_openai_generate_with_levels] Error processing OpenAI response: {e}")
        return []


def _find_closest_level(provided_level: str, valid_levels: list[str]) -> str:
    """Find the closest matching educational level from valid options."""
    provided_lower = provided_level.lower()

    # Direkte Übereinstimmung
    for level in valid_levels:
        if level.lower() == provided_lower:
            return level

    # Teilstring-Übereinstimmung
    for level in valid_levels:
        if provided_lower in level.lower() or level.lower() in provided_lower:
            return level

    # Fallback: Erste verfügbare Bildungsstufe
    logger.warning(f"Could not match '{provided_level}' to valid levels {valid_levels}, using '{valid_levels[0]}'")
    return valid_levels[0]
