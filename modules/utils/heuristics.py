"""Deterministic heuristics: repetition, readability, coreference, dangling modifiers."""

from __future__ import annotations

import re
import math
from collections import Counter
from typing import Optional

from modules.models import (
    RepetitionItem, ReadabilityMetrics, CoreferenceFlag, DanglingModifierFlag,
)
from modules.utils.segmentation import split_sentences, count_words


# ── Repetition detection ─────────────────────────────────────────────────

_STOP_WORDS_EN = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "out",
    "off", "over", "under", "again", "further", "then", "once", "and",
    "but", "or", "nor", "not", "no", "so", "if", "it", "its", "this",
    "that", "these", "those", "he", "she", "they", "we", "you", "i",
    "me", "him", "her", "us", "them", "my", "your", "his", "our",
    "their", "what", "which", "who", "whom", "how", "when", "where",
    "why", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "only", "own", "same", "than", "too",
    "very", "just", "about", "up",
})

_STOP_WORDS_RU = frozenset({
    "и", "в", "на", "с", "не", "что", "он", "она", "они", "мы", "вы",
    "я", "это", "но", "по", "к", "из", "у", "за", "от", "до", "о",
    "же", "ли", "бы", "да", "нет", "так", "как", "все", "был", "была",
    "было", "были", "быть", "его", "её", "их", "ее", "мой", "мне",
    "мной", "тот", "та", "то", "те", "этот", "эта", "эти", "этого",
    "для", "при", "через", "после", "перед", "между", "во", "со",
    "уже", "ещё", "еще", "тоже", "также", "только", "если", "чем",
    "когда", "где", "кто", "чей", "свой", "себя", "сам", "сама",
    "весь", "вся", "всё", "вот", "ни", "даже",
})


def detect_repetitions(
    paragraphs: list[str],
    language: str = "en",
    min_count: int = 3,
    ngram_sizes: tuple[int, ...] = (2, 3),
) -> list[RepetitionItem]:
    """Find repeated word n-grams across paragraphs."""
    stop = _STOP_WORDS_RU if language == "ru" else _STOP_WORDS_EN
    ngram_locations: dict[str, list[int]] = {}

    for pi, para in enumerate(paragraphs):
        words = re.findall(r'\b\w+\b', para.lower())
        for n in ngram_sizes:
            for i in range(len(words) - n + 1):
                gram = tuple(words[i:i + n])
                if all(w in stop for w in gram):
                    continue
                key = " ".join(gram)
                ngram_locations.setdefault(key, []).append(pi)

    results = []
    for phrase, locs in ngram_locations.items():
        if len(locs) >= min_count:
            results.append(RepetitionItem(
                phrase=phrase,
                count=len(locs),
                locations=sorted(set(locs)),
            ))

    results.sort(key=lambda r: r.count, reverse=True)
    return results[:30]


def detect_word_repetitions(
    paragraphs: list[str],
    language: str = "en",
    min_count: int = 5,
) -> list[RepetitionItem]:
    """Find single words repeated excessively."""
    stop = _STOP_WORDS_RU if language == "ru" else _STOP_WORDS_EN
    word_locs: dict[str, list[int]] = {}

    for pi, para in enumerate(paragraphs):
        words = re.findall(r'\b\w+\b', para.lower())
        for w in words:
            if w in stop or len(w) < 3:
                continue
            word_locs.setdefault(w, []).append(pi)

    results = []
    for word, locs in word_locs.items():
        if len(locs) >= min_count:
            results.append(RepetitionItem(
                phrase=word,
                count=len(locs),
                locations=sorted(set(locs)),
            ))

    results.sort(key=lambda r: r.count, reverse=True)
    return results[:20]


# ── Readability metrics ──────────────────────────────────────────────────

def compute_readability(text: str, language: str = "en") -> ReadabilityMetrics:
    """Compute basic readability statistics."""
    sentences = split_sentences(text)
    words = re.findall(r'\b\w+\b', text)

    if not words or not sentences:
        return ReadabilityMetrics()

    word_count = len(words)
    sentence_count = len(sentences)
    avg_sentence_length = word_count / sentence_count

    syllable_counts = [_count_syllables(w, language) for w in words]
    total_syllables = sum(syllable_counts)
    avg_word_length = sum(len(w) for w in words) / word_count

    sent_lengths = [count_words(s) for s in sentences]
    long_count = sum(1 for sl in sent_lengths if sl > 25)
    very_long_count = sum(1 for sl in sent_lengths if sl > 40)

    unique_words = len(set(w.lower() for w in words))
    vocab_richness = unique_words / word_count if word_count else 0.0

    flesch: Optional[float] = None
    if language == "en" and sentence_count > 0 and word_count > 0:
        flesch = 206.835 - 1.015 * avg_sentence_length - 84.6 * (total_syllables / word_count)
        flesch = round(flesch, 1)

    return ReadabilityMetrics(
        avg_sentence_length=round(avg_sentence_length, 1),
        avg_word_length=round(avg_word_length, 2),
        long_sentence_count=long_count,
        very_long_sentence_count=very_long_count,
        vocabulary_richness=round(vocab_richness, 4),
        flesch_reading_ease=flesch,
    )


def _count_syllables(word: str, language: str = "en") -> int:
    """Rough syllable count heuristic."""
    word = word.lower().strip()
    if not word:
        return 0

    if language == "ru":
        return sum(1 for c in word if c in "аеёиоуыэюяaeiouy")

    vowels = "aeiouy"
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel

    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


# ── Coreference flags ───────────────────────────────────────────────────

_PRONOUNS_EN = {"he", "she", "it", "they", "him", "her", "them", "his", "its", "their"}
_PRONOUNS_RU = {"он", "она", "оно", "они", "его", "её", "ее", "их", "ему", "ей", "им", "ним", "ней", "них"}

_CAPITALIZED_PRONOUNS_EN = {
    "He", "She", "It", "They", "Him", "Her", "Them", "His", "Its", "Their",
    "The", "This", "That", "These", "Those", "There", "Here",
    "My", "Your", "Our", "We", "You", "I",
    "What", "Which", "Who", "How", "When", "Where", "Why",
    "And", "But", "Or", "So", "If", "As", "In", "On", "At", "To", "For",
    "Not", "No", "Yes",
}
_CAPITALIZED_PRONOUNS_RU = {
    "Он", "Она", "Оно", "Они", "Его", "Её", "Ее", "Их", "Ему", "Ей",
    "Им", "Ним", "Ней", "Них", "Это", "Тот", "Та", "То", "Те",
    "Мой", "Мне", "Мой", "Мне", "Ваш", "Наш", "Мы", "Вы", "Я",
    "Что", "Кто", "Как", "Где", "Когда", "Зачем", "Почему",
    "И", "Но", "Или", "Если", "Да", "Нет", "Вот", "Уже",
}

_NOUNS_HINT_EN = re.compile(r'\b[A-Z][a-z]+\b')
_NOUNS_HINT_RU = re.compile(r'\b[А-ЯЁ][а-яё]+\b')


def detect_coreference_flags(
    paragraphs: list[str],
    language: str = "en",
    window: int = 2,
) -> list[CoreferenceFlag]:
    """
    Flag pronouns that appear without a plausible antecedent
    in the surrounding sentence window.
    """
    pronouns = _PRONOUNS_RU if language == "ru" else _PRONOUNS_EN
    noun_pat = _NOUNS_HINT_RU if language == "ru" else _NOUNS_HINT_EN
    non_nouns = _CAPITALIZED_PRONOUNS_RU if language == "ru" else _CAPITALIZED_PRONOUNS_EN

    flags: list[CoreferenceFlag] = []

    for pi, para in enumerate(paragraphs):
        sents = split_sentences(para)
        for si, sent in enumerate(sents):
            words = re.findall(r'\b\w+\b', sent.lower())
            sent_pronouns = [w for w in words if w in pronouns]
            if not sent_pronouns:
                continue

            context_start = max(0, si - window)
            context_end = min(len(sents), si + window + 1)
            context_text = " ".join(sents[context_start:context_end])

            raw_matches = noun_pat.findall(context_text)
            nouns_in_context = [m for m in raw_matches if m not in non_nouns]

            if not nouns_in_context:
                if pi == 0 and si == 0:
                    for pn in sent_pronouns:
                        flags.append(CoreferenceFlag(
                            pronoun=pn,
                            paragraph_index=pi,
                            sentence_index=si,
                            context=sent[:100],
                            issue=f"Pronoun '{pn}' appears at the very start with no prior antecedent",
                        ))
                elif pi == 0 and si <= 1:
                    for pn in sent_pronouns:
                        flags.append(CoreferenceFlag(
                            pronoun=pn,
                            paragraph_index=pi,
                            sentence_index=si,
                            context=sent[:100],
                            issue=f"Pronoun '{pn}' appears early with no clear antecedent in context",
                        ))

    return flags[:20]


# ── Dangling modifier detection ─────────────────────────────────────────

_DANGLING_EN = re.compile(
    r'^(Having\s+\w+|Being\s+\w+|Walking\s+\w+|Looking\s+\w+|'
    r'Running\s+\w+|Sitting\s+\w+|Standing\s+\w+|Lying\s+\w+|'
    r'Made\s+\w+|Born\s+\w+|Driven\s+\w+|Raised\s+\w+|'
    r'\w+ing\s+(?:to|at|in|on|with|from)\s+\w+),\s+'
    r'(?:the\s+\w+|a\s+\w+|an\s+\w+|it\s+)',
    re.IGNORECASE
)

_DANGLING_RU = re.compile(
    r'^(Будучи\s+\w+|Имея\s+\w+|Находясь\s+\w+|Являясь\s+\w+|'
    r'\w+(?:вши|вшись|ши|в)\s+\w+),\s+',
    re.IGNORECASE
)


def detect_dangling_modifiers(
    paragraphs: list[str],
    language: str = "en",
) -> list[DanglingModifierFlag]:
    """Best-effort detection of dangling/misplaced modifiers."""
    pattern = _DANGLING_RU if language == "ru" else _DANGLING_EN
    flags: list[DanglingModifierFlag] = []

    for pi, para in enumerate(paragraphs):
        sents = split_sentences(para)
        for sent in sents:
            m = pattern.search(sent)
            if m:
                flags.append(DanglingModifierFlag(
                    modifier=m.group(1),
                    paragraph_index=pi,
                    sentence=sent[:150],
                    issue="Possible dangling modifier: the introductory phrase "
                          "may not correctly modify the subject that follows.",
                ))

    return flags[:15]
