"""Text segmentation: paragraphs, sentences, and words.

Uses razdel for Russian-aware tokenization when available,
falls back to regex-based splitting.
"""

from __future__ import annotations

import re

try:
    from razdel import sentenize as _razdel_sentenize
    from razdel import tokenize as _razdel_tokenize
    _HAS_RAZDEL = True
except ImportError:
    _HAS_RAZDEL = False

_SENTENCE_SPLIT = re.compile(
    r'(?<=[.!?…»\u0022\u201d])\s+(?=[A-ZА-ЯЁ\u00C0-\u00DC\u0400-\u042F\u201c\u00AB\u0022])'
)

_ABBREVIATIONS = {
    "mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.",
    "т.е.", "т.д.", "т.п.", "др.", "гг.", "г.", "стр.",
    "и.о.", "напр.", "ок.",
}


def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs by blank lines or double newlines."""
    raw = re.split(r'\n\s*\n|\r\n\s*\r\n', text.strip())
    return [p.strip() for p in raw if p.strip()]


def split_sentences(text: str) -> list[str]:
    """
    Split a block of text into individual sentences.

    Uses razdel (Russian-aware) when available, falls back to regex.
    """
    text = text.strip()
    if not text:
        return []

    if _HAS_RAZDEL:
        return [s.text.strip() for s in _razdel_sentenize(text) if s.text.strip()]

    # Fallback: regex-based splitting
    parts = _SENTENCE_SPLIT.split(text)
    sentences: list[str] = []
    buffer = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if buffer:
            lower_buf = buffer.lower()
            if any(lower_buf.endswith(abbr) for abbr in _ABBREVIATIONS):
                buffer = buffer + " " + part
                continue
            sentences.append(buffer)
            buffer = part
        else:
            buffer = part

    if buffer:
        sentences.append(buffer)

    return sentences


def tokenize_words(text: str) -> list[str]:
    """
    Tokenize text into words (excluding punctuation).

    Uses razdel when available for better Russian tokenization.
    """
    if _HAS_RAZDEL:
        return [t.text for t in _razdel_tokenize(text)
                if re.match(r'\w', t.text)]

    return re.findall(r'\b\w+\b', text)


def count_words(text: str) -> int:
    """Count words in text."""
    return len(tokenize_words(text))
