"""Utility helper functions: split, synonyms, translate.

These are lightweight placeholders to satisfy the MVP util endpoints. They can
later be replaced with more sophisticated implementations or external APIs.
"""

from __future__ import annotations

import re

from loguru import logger

# Import functions that will be used later
from .openai_wrapper import generate_synonyms_llm as _synonyms_llm
from .openai_wrapper import translate_text as _translate_text

# Logging via loguru (see plan.md for style)


def _clean_text_for_json(text: str) -> str:
    """Clean text to be JSON-safe by removing/replacing invalid control characters."""
    if not text:
        return text

    # Remove or replace problematic control characters
    # Keep common whitespace characters (space, tab, newline, carriage return)
    cleaned = ""
    for char in text:
        # Allow printable characters and common whitespace
        if char.isprintable() or char in "\t\n\r":
            cleaned += char
        else:
            # Replace control characters with space
            cleaned += " "

    # Normalize multiple whitespace to single spaces
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def split_text(
    text: str,
    chunk_size: int = 200,
    overlap: int = 50,
    *,
    preserve_sentences: bool = True,
) -> list[str]:
    """Split text into overlapping chunks with sentence preservation.

    Parameters
    ----------
    text : str
        Input string.
    chunk_size : int, default 200
        Target size of each chunk (characters).
    overlap : int, default 50
        If > 0, create overlapping context between consecutive chunks.
    preserve_sentences : bool, default True
        Whether to preserve sentence boundaries when splitting.
    """
    logger.info(
        f"[split_text] Called with chunk_size={chunk_size}, overlap={overlap}, "
        f"preserve_sentences={preserve_sentences}"
    )
    logger.debug(f"[split_text] Input text length: {len(text) if text else 0}")
    text = text.strip()
    if not text:
        logger.info("[split_text] Empty input text. Returning empty list.")
        return []

    if chunk_size <= 0:
        logger.error(f"[split_text] Invalid chunk_size: {chunk_size}")
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        logger.error(f"[split_text] Invalid overlap: {overlap} (chunk_size={chunk_size})")
        raise ValueError("0 <= overlap < chunk_size required")
    # Choose splitting mode based on preserve_sentences parameter
    if not preserve_sentences:
        # Character mode - simple chunking
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(_clean_text_for_json(text[start:end]))
            start = end - overlap  # move with overlap
        logger.info(f"[split_text] Returning {len(chunks)} chunks (char mode)")
        return chunks

    # sentence mode (default)
    sentences = re.split(r"(?<=[.!?]) +", text)
    sentence_chunks: list[str] = []
    current = ""
    last_sentences = []  # Keep track of sentences in current chunk

    for s in sentences:
        s = s.strip()
        if not s:
            continue

        if len(current) + len(s) + 1 <= chunk_size:
            current += (" " if current else "") + s
            last_sentences.append(s)
        else:
            if current:
                sentence_chunks.append(_clean_text_for_json(current))

            # Handle overlap for sentence mode
            if overlap > 0 and last_sentences:
                # Calculate how many characters we want to overlap
                overlap_text = ""
                overlap_length = 0

                # Add sentences from the end of last chunk until we reach desired overlap
                for i in range(len(last_sentences) - 1, -1, -1):
                    sentence = last_sentences[i]
                    if overlap_length + len(sentence) + 1 <= overlap:
                        overlap_text = sentence + (" " + overlap_text if overlap_text else "")
                        overlap_length += len(sentence) + (1 if overlap_text != sentence else 0)
                    else:
                        break

                # Start new chunk with overlap + current sentence
                if overlap_text:
                    current = overlap_text + " " + s
                    # Keep track of overlapped sentences plus new one
                    overlap_sentences = [sent for sent in last_sentences if sent in overlap_text]
                    last_sentences = [*overlap_sentences, s]
                else:
                    current = s
                    last_sentences = [s]
            else:
                current = s
                last_sentences = [s]

    if current:
        sentence_chunks.append(_clean_text_for_json(current))

    logger.info(f"[split_text] Returning {len(sentence_chunks)} chunks (sentence mode)")
    return sentence_chunks


_simple_synonyms = {
    "Berg": ["Gebirge", "Erhebung"],
    "hoch": ["groß", "erhaben"],
}


def generate_synonyms(word: str, max_synonyms: int = 5, *, lang: str = "de") -> list[str]:
    """Return synonyms via OpenAI - fallback to local dict."""
    logger.info(
        f"[generate_synonyms] Called with word='{word}', max_synonyms={max_synonyms}, lang='{lang}'"
    )
    try:
        syns = _synonyms_llm(word, max_synonyms=max_synonyms, lang=lang)
        if syns:
            logger.info(f"[generate_synonyms] Found {len(syns)} synonyms via OpenAI for '{word}'")
            return syns
    except Exception as exc:
        logger.warning(f"[generate_synonyms] OpenAI fallback for word '{word}': {exc}")
    fallback_syns = _simple_synonyms.get(word, [])[:max_synonyms]
    logger.info(
        f"[generate_synonyms] Returning {len(fallback_syns)} fallback synonyms for '{word}'"
    )
    return fallback_syns


def translate(text: str, target_lang: str = "en", source_lang: str | None = None) -> str:
    """Translate text to target language via OpenAI.

    Parameters
    ----------
    text : str
        Text to translate
    target_lang : str, default "en"
        Target language code (e.g., "en", "de")
    source_lang : str, optional
        Source language code if known

    Returns
    -------
    str
        Translated text or fallback message if translation fails

    Falls back to returning the original text if OpenAI is not configured.
    """
    logger.info(f"[translate] Called with target_lang='{target_lang}', source_lang='{source_lang}'")
    logger.debug(f"[translate] Input text length: {len(text) if text else 0}")
    try:
        # Pass source_lang if provided
        kwargs = {"target_lang": target_lang}
        if source_lang:
            kwargs["source_lang"] = source_lang

        out = _translate_text(text, **kwargs)

        if out and out.strip() != text.strip():  # Check for actual translation
            logger.info(f"[translate] Successfully translated text to '{target_lang}'")
            return out
        logger.info(f"[translate] No translation performed, returning fallback for '{target_lang}'")
        return f"[{target_lang} translation of]: {text}"
    except Exception as exc:  # Catch any exception for robust fallback
        logger.warning(f"[translate] OpenAI fallback for target_lang='{target_lang}': {exc}")
        return f"[{target_lang} translation of]: {text}"
