"""
Auto-generate baseline analysis requirements when none are provided by the user.

Uses deterministic analysis results to build context-aware requirements
that guide the LLM toward specific, actionable critique.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from modules.models import DeterministicAnalysis

logger = logging.getLogger("prose-critique")

# ── Baseline requirements that apply to ANY prose text ─────────────────

_BASELINE_EN = [
    "Comprehensibility: Is the text understandable on first reading? Flag any phrases or passages that may confuse a general reader.",
    "Clarity of expression: Identify vague, ambiguous, or unnecessarily convoluted sentences. Suggest simpler alternatives where possible.",
    "Sentence complexity: Flag overly long compound/complex sentences that could be split for readability without losing meaning.",
    "Excessive pathos or pomposity: Detect bombastic, excessively solemn, or melodramatic phrasing that feels unearned by the content.",
    "Stylistic affectation: Identify pretentious, overly ornate, or deliberately obscure word choices that hinder readability.",
    "Clichés and stock phrases: Find worn-out expressions, trite metaphors, and filler phrases. Suggest fresher alternatives.",
    "Logical consistency: Check for contradictions, implausible descriptions, or factual impossibilities within the text's own universe.",
    "Terminology burden: Flag specialized terms, jargon, or archaisms that are used without explanation and may alienate readers.",
    "Realistic descriptions: Assess whether physical descriptions, character actions, and scene details are plausible and internally consistent.",
    "Pacing and rhythm: Evaluate whether the text flows naturally or has jarring transitions, rushed passages, or unnecessary digressions.",
    "Pronoun clarity: Check that every pronoun has a clear antecedent. Flag cases where 'he', 'she', 'it', or 'they' could refer to multiple entities.",
    "Redundancy: Identify tautologies, repetitive ideas, and sentences that could be removed without information loss.",
    "Voice consistency: Does the narrative voice stay consistent throughout, or are there shifts in register, tense, or person?",
    "Dialogue naturalness: If dialogue is present, does it sound like real speech? Is it distinctive to characters?",
    "Emotional impact: Does the text evoke the intended emotional response, or does it fall flat / overshoot?",
]

_BASELINE_RU = [
    "Понятность: Понятен ли текст при первом прочтении? Отметьте фразы или отрывки, которые могут запутать читателя.",
    "Ясность изложения: Определите расплывчатые, двусмысленные или излишне запутанные предложения. Предложите более простые формулировки.",
    "Сложность предложений: Отметьте чрезмерно длинные сложносочинённые/сложноподчинённые предложения, которые можно разбить без потери смысла.",
    "Излишний пафос: Обнаружьте напыщенные, чрезмерно торжественные или мелодраматичные формулировки, не оправданные содержанием.",
    "Вычурность стиля: Определите претенциозные, нарочито витиеватые или намеренно непонятные словесные конструкции, мешающие чтению.",
    "Клише и штампы: Найдите затёртые выражения, банальные метафоры и слова-паразиты. Предложите более свежие альтернативы.",
    "Логическая непротиворечивость: Проверьте, нет ли противоречий, неправдоподобных описаний или фактических невозможностей во внутренней логике текста.",
    "Терминологическая нагрузка: Отметьте специальные термины, жаргон или архаизмы, использованные без объяснения и способные оттолкнуть читателя.",
    "Реалистичность описаний: Оцените, правдоподобны ли физические описания, действия персонажей и детали сцен, последовательны ли они.",
    "Темп и ритм: Оцените, течёт ли текст естественно или в нём есть резкие переходы, скомканные фрагменты, лишние отступления.",
    "Ясность местоимений: Проверьте, что у каждого местоимения есть однозначный антецедент. Отметьте случаи, где «он», «она», «оно» могут относиться к нескольким сущностям.",
    "Избыточность: Определите тавтологии, повторяющиеся мысли и предложения, которые можно убрать без потери информации.",
    "Единство голоса: Сохраняется ли повествовательный голос на протяжении текста, или есть скачки регистра, времени или лица?",
    "Естественность диалогов: Если в тексте есть диалоги, звучат ли они как реальная речь? Различаются ли реплики персонажей?",
    "Эмоциональное воздействие: Вызывает ли текст задуманную эмоциональную реакцию, или он недотягивает / перебарщивает?",
]

# ── Conditional requirements triggered by deterministic analysis ───────


def generate_auto_requirements(
    deterministic: DeterministicAnalysis,
    text: str,
) -> str:
    """
    Generate a structured set of analysis requirements based on
    deterministic pre-analysis of the text.

    Returns a formatted requirements string (in the text's language).
    """
    lang = deterministic.language
    is_ru = lang == "ru"

    sections: list[str] = []

    # Header
    if is_ru:
        sections.append("=== АВТОМАТИЧЕСКИ СГЕНЕРИРОВАННЫЕ ТРЕБОВАНИЯ К АНАЛИЗУ ===")
        sections.append(
            "(Требования пользователя не указаны. Ниже — базовый набор критериев, "
            "дополненный результатами предварительного анализа текста.)\n"
        )
    else:
        sections.append("=== AUTO-GENERATED ANALYSIS REQUIREMENTS ===")
        sections.append(
            "(No user requirements provided. Below is a baseline set of criteria, "
            "augmented by pre-analysis results.)\n"
        )

    # Baseline requirements
    baseline = _BASELINE_RU if is_ru else _BASELINE_EN
    if is_ru:
        sections.append("## Базовые критерии анализа\n")
    else:
        sections.append("## Baseline Analysis Criteria\n")

    for i, req in enumerate(baseline, 1):
        sections.append(f"{i}. {req}")

    sections.append("")

    # Conditional requirements based on what the deterministic analysis found
    conditional = _build_conditional_requirements(deterministic, text, is_ru)
    if conditional:
        if is_ru:
            sections.append("## Дополнительные критерии (на основе предварительного анализа)\n")
        else:
            sections.append("## Additional Criteria (based on pre-analysis)\n")
        for i, req in enumerate(conditional, len(baseline) + 1):
            sections.append(f"{i}. {req}")
        sections.append("")

    # Text-type specific requirements
    type_reqs = _detect_text_type_requirements(text, is_ru)
    if type_reqs:
        if is_ru:
            sections.append("## Критерии по типу текста\n")
        else:
            sections.append("## Text-Type Specific Criteria\n")
        n = len(baseline) + len(conditional)
        for i, req in enumerate(type_reqs, n + 1):
            sections.append(f"{i}. {req}")
        sections.append("")

    result = "\n".join(sections)
    logger.info(
        "Auto-generated %d requirements (%d baseline + %d conditional + %d type-specific)",
        len(baseline) + len(conditional) + len(type_reqs),
        len(baseline), len(conditional), len(type_reqs),
    )
    return result


def _build_conditional_requirements(
    det: DeterministicAnalysis,
    text: str,
    is_ru: bool,
) -> list[str]:
    """Build requirements triggered by specific findings in the text."""
    reqs: list[str] = []
    r = det.readability

    # Long sentences detected
    if r.long_sentence_count > 0:
        if is_ru:
            reqs.append(
                f"ВНИМАНИЕ — длинные предложения: обнаружено {r.long_sentence_count} предложений "
                f"длиннее 25 слов. Оцените, можно ли их разбить без потери смысла."
            )
        else:
            reqs.append(
                f"ATTENTION — long sentences: {r.long_sentence_count} sentences over 25 words found. "
                f"Assess whether they can be split without losing meaning."
            )

    # Very long sentences
    if r.very_long_sentence_count > 0:
        if is_ru:
            reqs.append(
                f"КРИТИЧНО — очень длинные предложения: {r.very_long_sentence_count} предложений "
                f"длиннее 40 слов. Такие предложения почти всегда можно упростить."
            )
        else:
            reqs.append(
                f"CRITICAL — very long sentences: {r.very_long_sentence_count} sentences over 40 words. "
                f"These can almost always be simplified."
            )

    # Low vocabulary richness (repetitive text)
    if r.vocabulary_richness < 0.6 and det.word_count > 50:
        if is_ru:
            reqs.append(
                f"Скудный словарный запас: богатство словаря {r.vocabulary_richness:.2f} "
                f"(норма > 0.60). Проверьте, не перегружен ли текст повторами."
            )
        else:
            reqs.append(
                f"Low vocabulary richness: {r.vocabulary_richness:.2f} (expected > 0.60). "
                f"Check if the text is overloaded with repetitions."
            )

    # High vocabulary richness (possibly too ornate)
    if r.vocabulary_richness > 0.90 and det.word_count > 100:
        if is_ru:
            reqs.append(
                "Очень высокое лексическое разнообразие: проверьте, не связано ли это "
                "с излишней вычурностью или использованием редких слов без необходимости."
            )
        else:
            reqs.append(
                "Very high lexical diversity: check whether this is due to excessive "
                "ornateness or unnecessary use of rare words."
            )

    # Repetitions found
    if det.repetitions:
        top_reps = [f'"{r.phrase}" ({r.count}x)' for r in det.repetitions[:5]]
        if is_ru:
            reqs.append(
                f"Обнаружены повторы: {', '.join(top_reps)}. "
                f"Оцените, оправданы ли повторы или их следует устранить."
            )
        else:
            reqs.append(
                f"Repetitions detected: {', '.join(top_reps)}. "
                f"Assess whether repetitions are intentional or should be eliminated."
            )

    # Coreference issues
    if det.coreference_flags:
        if is_ru:
            reqs.append(
                f"Обнаружены {len(det.coreference_flags)} потенциальных проблем "
                f"с местоимениями. Тщательно проверьте, кто/что имеется в виду в каждом случае."
            )
        else:
            reqs.append(
                f"Found {len(det.coreference_flags)} potential pronoun reference issues. "
                f"Carefully verify who/what is referred to in each case."
            )

    # Dangling modifiers
    if det.dangling_modifier_flags:
        if is_ru:
            reqs.append(
                f"Обнаружены {len(det.dangling_modifier_flags)} возможных висячих модификаторов. "
                f"Проверьте, правильно ли согласованы причастные и деепричастные обороты."
            )
        else:
            reqs.append(
                f"Found {len(det.dangling_modifier_flags)} possible dangling modifiers. "
                f"Verify that participial phrases correctly modify their subjects."
            )

    # Short text (fragment)
    if det.word_count < 100:
        if is_ru:
            reqs.append(
                "Короткий текст (менее 100 слов): учитывайте, что это может быть "
                "фрагмент, вырванный из контекста. Не наказывайте за отсутствие завершённости."
            )
        else:
            reqs.append(
                "Short text (under 100 words): consider that this may be a fragment "
                "taken out of context. Do not penalize for lack of completeness."
            )

    # Short paragraphs (could indicate dialogue-heavy text)
    if det.paragraph_count > 0:
        avg_para_len = det.word_count / det.paragraph_count
        if avg_para_len < 15 and det.paragraph_count > 5:
            if is_ru:
                reqs.append(
                    "Много коротких абзацев: текст может содержать много диалогов. "
                    "Оцените качество диалогов и их вклад в повествование."
                )
            else:
                reqs.append(
                    "Many short paragraphs: the text may be dialogue-heavy. "
                    "Evaluate dialogue quality and its contribution to the narrative."
                )

    return reqs


def _detect_text_type_requirements(text: str, is_ru: bool) -> list[str]:
    """Detect text type from content signals and add targeted requirements."""
    reqs: list[str] = []

    has_dialogue = bool(re.search(r'[—–-]\s', text)) or '"' in text or '«' in text
    has_description = len(text) > 300 and not has_dialogue

    # Check for fairy-tale / fantasy markers
    fantasy_markers_ru = ["фея", "фей", "эльф", "маг", "волшеб", "зелье", "снадобье",
                          "замок", "дракон", "кот учёный", "заклинан", "нимф", "паж",
                          "бал", "чудес", "колдов"]
    fantasy_markers_en = ["fairy", "elf", "elves", "wizard", "magic", "potion",
                          "castle", "dragon", "spell", "enchant", "nymph", "ball",
                          "wondrous", "sorcerer"]

    lower_text = text.lower()
    markers = fantasy_markers_ru if is_ru else fantasy_markers_en
    fantasy_count = sum(1 for m in markers if m in lower_text)

    if fantasy_count >= 2:
        if is_ru:
            reqs.append(
                "Текст содержит элементы фэнтези/сказки. Оцените: (a) внутреннюю "
                "логику магической системы, (b) баланс между сказочностью и понятностью, "
                "(c) не становится ли стилизация помехой для чтения."
            )
        else:
            reqs.append(
                "Text contains fantasy/fairy-tale elements. Assess: (a) internal "
                "logic of the magical system, (b) balance between whimsy and clarity, "
                "(c) whether stylization hinders readability."
            )

    if has_dialogue:
        if is_ru:
            reqs.append(
                "Текст содержит диалоги. Оцените: (a) естественность реплик, "
                "(b) различимость голосов персонажей, (c) вклад диалогов в развитие сюжета."
            )
        else:
            reqs.append(
                "Text contains dialogue. Assess: (a) naturalness of speech, "
                "(b) distinctiveness of character voices, (c) contribution to plot."
            )

    # Check for children's literature markers
    children_markers_ru = ["феечка", "котик", "зайчик", "дорожк", "полянк",
                           "тропинк", "избушк", "сказк", "ёжик"]
    children_markers_en = ["little", "fairy", "bunny", "cottage", "meadow",
                           "path", "tale"]

    child_markers = children_markers_ru if is_ru else children_markers_en
    child_count = sum(1 for m in child_markers if m in lower_text)

    if child_count >= 2:
        if is_ru:
            reqs.append(
                "Возможно, текст для детской/юношеской аудитории. Оцените "
                "соответствие лексики и конструкций целевому возрасту."
            )
        else:
            reqs.append(
                "Possibly children's/young adult literature. Assess "
                "whether vocabulary and constructions match the target age."
            )

    # Check for archaic / stylized language
    archaic_ru = ["эдакую", "нынче", "токмо", "оный", "сей", "дабы", "ибо",
                  "чело", "уста", "молвил", "рёк", "приметила", "бедняжка",
                  "запамятовала", "дивно", "сделалась"]
    archaic_en = ["hath", "thou", "doth", "wherefore", "forsooth", "thine",
                  "whilst", "ere", "betwixt", "perchance"]

    arch_markers = archaic_ru if is_ru else archaic_en
    arch_count = sum(1 for m in arch_markers if m in lower_text)

    if arch_count >= 2:
        if is_ru:
            reqs.append(
                f"Обнаружены {arch_count} архаизмов/стилизованных слов. Оцените: "
                f"(a) уместность архаичной лексики, (b) не создаёт ли она барьер "
                f"для понимания, (c) последовательна ли стилизация на протяжении текста."
            )
        else:
            reqs.append(
                f"Found {arch_count} archaic/stylized words. Assess: "
                f"(a) appropriateness of archaic vocabulary, (b) whether it creates "
                f"a comprehension barrier, (c) consistency of stylization."
            )

    return reqs
