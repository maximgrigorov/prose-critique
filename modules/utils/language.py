"""Language detection (deterministic, no LLM)."""

from __future__ import annotations

import re

from langdetect import detect_langs, LangDetectException
from langdetect import DetectorFactory

DetectorFactory.seed = 0

_CYRILLIC_RATIO_THRESHOLD = 0.3
_CYRILLIC_RE = re.compile(r'[а-яёА-ЯЁ]')


def detect_language(text: str) -> tuple[str, float]:
    """
    Detect the dominant language of *text*.

    Returns:
        (iso_code, confidence)  e.g. ("ru", 0.98) or ("en", 0.95).
        Falls back to ("en", 0.0) on failure.
    """
    if not text or not text.strip():
        return "en", 0.0

    alpha_chars = re.findall(r'[a-zA-Zа-яёА-ЯЁ]', text)
    if alpha_chars:
        cyrillic_count = sum(1 for c in alpha_chars if _CYRILLIC_RE.match(c))
        cyrillic_ratio = cyrillic_count / len(alpha_chars)
        if cyrillic_ratio > _CYRILLIC_RATIO_THRESHOLD:
            return "ru", round(cyrillic_ratio, 4)

    try:
        results = detect_langs(text)
        if results:
            top = results[0]
            lang = str(top.lang)
            if lang in ("bg", "mk", "uk") and _has_cyrillic(text):
                return "ru", round(float(top.prob), 4)
            return lang, round(float(top.prob), 4)
    except LangDetectException:
        pass

    return "en", 0.0


def _has_cyrillic(text: str) -> bool:
    """Check if text contains Cyrillic characters."""
    return bool(_CYRILLIC_RE.search(text))


def language_name(code: str) -> str:
    """Human-readable language name for common codes."""
    names = {
        "en": "English",
        "ru": "Russian",
        "de": "German",
        "fr": "French",
        "es": "Spanish",
        "it": "Italian",
        "pt": "Portuguese",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
    }
    return names.get(code, code.upper())
