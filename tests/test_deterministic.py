"""Unit tests for deterministic analyzers."""

import pytest

from modules.utils.language import detect_language, language_name
from modules.utils.segmentation import split_paragraphs, split_sentences, count_words
from modules.utils.heuristics import (
    detect_repetitions,
    detect_word_repetitions,
    compute_readability,
    detect_coreference_flags,
)
from modules.agents.deterministic_analyzers import run_deterministic_analysis


# ── Language detection ────────────────────────────────────────────────────

class TestLanguageDetection:
    def test_english(self):
        lang, conf = detect_language(
            "The old man sat on the porch watching the sunset over the hills."
        )
        assert lang == "en"
        assert conf > 0.5

    def test_russian(self):
        lang, conf = detect_language(
            "Старик сидел на крыльце и смотрел на закат над холмами."
        )
        assert lang == "ru"
        assert conf > 0.5

    def test_empty(self):
        lang, conf = detect_language("")
        assert lang == "en"
        assert conf == 0.0

    def test_language_name(self):
        assert language_name("en") == "English"
        assert language_name("ru") == "Russian"
        assert language_name("xx") == "XX"


# ── Segmentation ─────────────────────────────────────────────────────────

class TestSegmentation:
    def test_split_paragraphs_basic(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        paras = split_paragraphs(text)
        assert len(paras) == 3
        assert paras[0] == "First paragraph."
        assert paras[2] == "Third paragraph."

    def test_split_paragraphs_empty_lines(self):
        text = "One.\n\n\n\nTwo."
        paras = split_paragraphs(text)
        assert len(paras) == 2

    def test_split_paragraphs_single(self):
        text = "Just one paragraph with no breaks."
        paras = split_paragraphs(text)
        assert len(paras) == 1

    def test_split_sentences_basic(self):
        text = "Hello world. This is a test. Another sentence here."
        sents = split_sentences(text)
        assert len(sents) >= 2

    def test_split_sentences_empty(self):
        assert split_sentences("") == []

    def test_count_words(self):
        assert count_words("Hello world foo bar") == 4
        assert count_words("") == 0
        assert count_words("one") == 1


# ── Repetition detection ─────────────────────────────────────────────────

class TestRepetition:
    def test_ngram_repetition(self):
        paragraphs = [
            "The big red dog ran fast.",
            "The big red cat sat still.",
            "The big red bird flew high.",
            "The big red fish swam deep.",
        ]
        reps = detect_repetitions(paragraphs, language="en", min_count=3)
        phrases = [r.phrase for r in reps]
        assert any("big red" in p for p in phrases)

    def test_word_repetition(self):
        paragraphs = [
            "dog dog dog dog dog",
            "another dog appeared",
        ]
        reps = detect_word_repetitions(paragraphs, language="en", min_count=5)
        assert any(r.phrase == "dog" for r in reps)

    def test_no_false_positives_on_stop_words(self):
        paragraphs = [
            "The the the the the.",
            "And and and and and.",
        ]
        reps = detect_repetitions(paragraphs, language="en", min_count=3)
        for r in reps:
            words = r.phrase.split()
            assert not all(w in {"the", "and", "a", "is"} for w in words)


# ── Readability ──────────────────────────────────────────────────────────

class TestReadability:
    def test_basic_metrics(self):
        text = "This is a simple sentence. Another one follows. Short and clear."
        metrics = compute_readability(text, language="en")
        assert metrics.avg_sentence_length > 0
        assert metrics.vocabulary_richness > 0

    def test_flesch_english(self):
        text = "The cat sat on the mat. The dog ran in the park. It was a sunny day."
        metrics = compute_readability(text, language="en")
        assert metrics.flesch_reading_ease is not None

    def test_flesch_not_for_russian(self):
        text = "Кот сидел на коврике. Собака бежала в парке."
        metrics = compute_readability(text, language="ru")
        assert metrics.flesch_reading_ease is None

    def test_long_sentences(self):
        text = " ".join(["word"] * 30) + ". " + " ".join(["another"] * 45) + "."
        metrics = compute_readability(text, language="en")
        assert metrics.long_sentence_count >= 1
        assert metrics.very_long_sentence_count >= 1


# ── Coreference flags ───────────────────────────────────────────────────

class TestCoreference:
    def test_pronoun_at_start(self):
        paragraphs = ["He walked into the room and sat down quietly."]
        flags = detect_coreference_flags(paragraphs, language="en")
        assert len(flags) > 0
        assert flags[0].pronoun == "he"

    def test_no_flag_with_antecedent(self):
        paragraphs = ["John walked into the room. He sat down quietly."]
        flags = detect_coreference_flags(paragraphs, language="en")
        assert len(flags) == 0

    def test_russian_pronoun(self):
        paragraphs = ["Он вошёл в комнату и тихо сел на стул."]
        flags = detect_coreference_flags(paragraphs, language="ru")
        assert len(flags) > 0
        assert flags[0].pronoun == "он"


# ── Full deterministic pipeline ──────────────────────────────────────────

class TestFullDeterministic:
    def test_english_text(self):
        text = (
            "The old man sat on the porch. He watched the sunset.\n\n"
            "His granddaughter brought tea. They sat in silence."
        )
        result = run_deterministic_analysis(text)
        assert result.language == "en"
        assert result.paragraph_count == 2
        assert result.word_count > 10
        assert result.char_count > 0

    def test_russian_text(self):
        text = (
            "Старик сидел на крыльце. Он смотрел на закат.\n\n"
            "Внучка принесла чай. Они сидели в тишине."
        )
        result = run_deterministic_analysis(text)
        assert result.language == "ru"
        assert result.paragraph_count == 2
