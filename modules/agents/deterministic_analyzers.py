"""Deterministic (non-LLM) text analysis pipeline."""

from __future__ import annotations

import logging

from modules.models import DeterministicAnalysis
from modules.utils.language import detect_language
from modules.utils.segmentation import split_paragraphs, split_sentences, count_words
from modules.utils.heuristics import (
    detect_repetitions,
    detect_word_repetitions,
    compute_readability,
    detect_coreference_flags,
    detect_dangling_modifiers,
)

logger = logging.getLogger("prose-critique")


def run_deterministic_analysis(text: str) -> DeterministicAnalysis:
    """
    Run all deterministic analyzers on the input text.
    No LLM calls. Pure local computation.
    """
    logger.info("Running deterministic analysis...")

    lang, lang_conf = detect_language(text)
    logger.info("Detected language: %s (confidence %.2f)", lang, lang_conf)

    paragraphs = split_paragraphs(text)
    all_sentences: list[str] = []
    for p in paragraphs:
        all_sentences.extend(split_sentences(p))

    word_count = count_words(text)
    char_count = len(text)

    ngram_reps = detect_repetitions(paragraphs, language=lang)
    word_reps = detect_word_repetitions(paragraphs, language=lang)
    all_reps = ngram_reps + word_reps

    seen_phrases: set[str] = set()
    deduped_reps = []
    for r in all_reps:
        if r.phrase not in seen_phrases:
            seen_phrases.add(r.phrase)
            deduped_reps.append(r)

    readability = compute_readability(text, language=lang)

    coref_flags = detect_coreference_flags(paragraphs, language=lang)
    dangling_flags = detect_dangling_modifiers(paragraphs, language=lang)

    result = DeterministicAnalysis(
        language=lang,
        language_confidence=lang_conf,
        paragraph_count=len(paragraphs),
        sentence_count=len(all_sentences),
        word_count=word_count,
        char_count=char_count,
        paragraphs=paragraphs,
        repetitions=deduped_reps,
        readability=readability,
        coreference_flags=coref_flags,
        dangling_modifier_flags=dangling_flags,
    )

    logger.info(
        "Deterministic analysis complete: %d paragraphs, %d sentences, %d words, "
        "%d repetitions, %d coref flags, %d dangling flags",
        result.paragraph_count, result.sentence_count, result.word_count,
        len(result.repetitions), len(result.coreference_flags),
        len(result.dangling_modifier_flags),
    )

    return result
