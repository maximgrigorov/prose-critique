"""Dynamic prompt generation for primary analyzer and auditor (EN/RU)."""

from __future__ import annotations

import json
from typing import Optional

from modules.models import DeterministicAnalysis

# ── Output schemas (for including in prompts) ────────────────────────────

PRIMARY_OUTPUT_SCHEMA = """{
  "text_overview": {
    "genre_guess": "<string>",
    "tone": "<string>",
    "apparent_audience": "<string>",
    "language": "<string>",
    "word_count": "<int>",
    "paragraph_count": "<int>"
  },
  "structural_outline": [
    {"paragraph_index": 0, "intent": "<string>", "summary": "<string>"}
  ],
  "local_issues": [
    {
      "paragraph_index": 0,
      "sentence": "<exact quote>",
      "issue_type": "<grammar|style|clarity|logic|word_choice|punctuation|redundancy|other>",
      "severity": "<minor|moderate|major|critical>",
      "description": "<detailed explanation>",
      "suggestion": "<concrete suggestion>"
    }
  ],
  "global_issues": [
    {
      "category": "<logic|pacing|voice|pov_consistency|character_consistency|contradictions|tone|other>",
      "severity": "<minor|moderate|major|critical>",
      "description": "<detailed explanation>",
      "evidence": "<quote or reference>"
    }
  ],
  "quality_scores": {
    "clarity": "<0.0-10.0>",
    "conciseness": "<0.0-10.0>",
    "vividness": "<0.0-10.0>",
    "originality": "<0.0-10.0>",
    "coherence": "<0.0-10.0>",
    "engagement": "<0.0-10.0>",
    "overall": "<0.0-10.0>"
  },
  "cliche_detection": [
    {"phrase": "<cliché phrase>", "location": "<paragraph N, sentence M>", "suggestion": "<alternative>"}
  ],
  "reader_questions": [
    {
      "question": "<what is unclear>",
      "location": "<paragraph N, sentence M>",
      "type": "<unclear_reference|missing_antecedent|undefined_term|logical_gap>"
    }
  ],
  "improvement_suggestions": [
    {"category": "<string>", "suggestion": "<string>", "priority": "<minor|moderate|major|critical>"}
  ],
  "strengths": ["<string>"],
  "summary": "<comprehensive summary of the critique>"
}"""

AUDIT_OUTPUT_SCHEMA = """{
  "audit_verdict": "<agree|mostly_agree|mixed|mostly_disagree|disagree>",
  "confidence_score": "<0.0-1.0>",
  "disagreements": [
    {
      "claim": "<the primary critique's claim>",
      "issue": "<what's wrong with the claim>",
      "evidence": "<quote from original text>",
      "severity": "<minor|moderate|major|critical>"
    }
  ],
  "missed_issues": [
    {
      "description": "<issue the primary critique missed>",
      "evidence": "<quote from original text>",
      "severity": "<minor|moderate|major|critical>"
    }
  ],
  "hallucinations": [
    {"claim": "<claim not supported by text>", "why_hallucinated": "<explanation>"}
  ],
  "weak_critiques": [
    {"claim": "<vague or generic claim>", "why_weak": "<explanation>"}
  ],
  "summary": "<overall assessment of the primary critique's quality>"
}"""


# ── English prompts ──────────────────────────────────────────────────────

_SYSTEM_PRIMARY_EN = """You are an expert literary critic, prose analyst, and writing coach with decades of experience.
Your task is to produce an EXTREMELY DETAILED, structured critique of the submitted text.

CRITICAL RULES:
1. You must NEVER rewrite or "fix" the text. Only ANALYZE and CRITIQUE.
2. Every claim must be backed by a SHORT QUOTE from the original text.
3. Be SPECIFIC and CONCRETE. Avoid generic praise or generic criticism.
4. Score honestly — do not inflate scores.
5. Actively look for "reader questions": places where a reader would be confused about who is being referred to, what a term means, or why something happened.
6. Check for clichés, tautologies, and overused phrases.
7. Assess logic, pacing, voice consistency, point-of-view consistency, and character consistency.
8. Identify contradictions, unclear antecedents, and dangling references.
9. Provide improvement suggestions as concise bullet points — not full rewrites.
10. Output ONLY valid JSON matching the schema below. No markdown code fences, no explanation outside JSON.
11. Your ENTIRE response must be a single JSON object. Start with { and end with }. No text before or after.
12. If author requirements are provided, evaluate the text against EACH requirement explicitly."""

_USER_PRIMARY_EN = """Analyze the following prose text and produce a detailed critique.

--- TEXT (input) ---
{text}
--- END TEXT ---

{requirements_block}

--- PRE-ANALYSIS (deterministic, for your reference) ---
{deterministic_summary}
--- END PRE-ANALYSIS ---

Output the critique as a single JSON object following this exact schema:
{schema}

Remember:
- Quote SHORT SPANS from the text as evidence.
- Be adversarial: find real problems, not just superficial ones.
- List "reader questions" — anything a first-time reader would find unclear.
- Score each dimension on a 0–10 scale. 10 = flawless. Most texts score 4–7.
- Ensure every local issue references a specific paragraph index and sentence."""


# ── Russian prompts ──────────────────────────────────────────────────────

_SYSTEM_PRIMARY_RU = """Вы — эксперт-литературный критик, аналитик прозы и литературный коуч с многолетним опытом.
Ваша задача — составить ИСКЛЮЧИТЕЛЬНО ПОДРОБНЫЙ структурированный критический разбор представленного текста.

КЛЮЧЕВЫЕ ПРАВИЛА:
1. Вы НЕ ДОЛЖНЫ переписывать или «исправлять» текст. Только АНАЛИЗИРОВАТЬ и КРИТИКОВАТЬ.
2. Каждое утверждение должно быть подкреплено КОРОТКОЙ ЦИТАТОЙ из оригинального текста.
3. Будьте КОНКРЕТНЫ. Избегайте общих похвал и общей критики.
4. Оценивайте честно — не завышайте оценки.
5. Активно ищите «вопросы читателя»: места, где читатель будет сбит с толку — о ком идёт речь? кто «он»? что значит этот термин?
6. Проверяйте клише, тавтологии и штампы.
7. Оцените логику, темп, последовательность голоса, точку зрения, непротиворечивость персонажей.
8. Выявляйте противоречия, неясные антецеденты, висячие ссылки.
9. Давайте рекомендации по улучшению в виде кратких пунктов — НЕ переписывайте текст.
10. Выводите ТОЛЬКО валидный JSON по схеме ниже. Без markdown-блоков кода, без пояснений за пределами JSON.
11. Весь ваш ответ должен быть ОДНИМ JSON-объектом. Начните с { и закончите }. Никакого текста до или после.
12. Если указаны требования автора, оценивайте текст по КАЖДОМУ требованию явно."""

_USER_PRIMARY_RU = """Проанализируйте следующий прозаический текст и составьте подробный критический разбор.

--- ТЕКСТ (входные данные) ---
{text}
--- КОНЕЦ ТЕКСТА ---

{requirements_block}

--- ПРЕДВАРИТЕЛЬНЫЙ АНАЛИЗ (детерминированный, для справки) ---
{deterministic_summary}
--- КОНЕЦ ПРЕДВАРИТЕЛЬНОГО АНАЛИЗА ---

Выведите критику в виде единого JSON-объекта по следующей схеме:
{schema}

Помните:
- Цитируйте КОРОТКИЕ ФРАГМЕНТЫ текста как доказательства.
- Будьте требовательны: ищите реальные проблемы, а не поверхностные.
- Перечислите «вопросы читателя» — всё, что при первом прочтении будет непонятно.
- Оценивайте каждое измерение по шкале 0–10. 10 = безупречно. Большинство текстов получают 4–7.
- Убедитесь, что каждая локальная проблема ссылается на конкретный индекс абзаца и предложение."""


# ── Auditor prompts ──────────────────────────────────────────────────────

_SYSTEM_AUDIT_EN = """You are an adversarial meta-reviewer. Your job is to rigorously audit a literary critique produced by another AI model.

YOUR MISSION:
1. Verify EVERY factual claim in the critique against the original text.
2. Detect HALLUCINATIONS: claims about the text that are simply false.
3. Identify MISSED ISSUES the critique failed to notice.
4. Flag WEAK or VAGUE critique points that lack specific evidence.
5. Check that quoted evidence actually exists in the text (no fabricated quotes).
6. Assess whether scores are fair and consistent with the issues found.
7. Provide a confidence score (0.0 = no confidence, 1.0 = full confidence in your audit).
8. Output ONLY valid JSON. No markdown code fences, no explanation outside JSON.
9. Your ENTIRE response must be a single JSON object. Start with { and end with }."""

_USER_AUDIT_EN = """Audit the following literary critique. Compare it against the original text.

--- ORIGINAL TEXT ---
{text}
--- END ORIGINAL TEXT ---

--- CRITIQUE TO AUDIT ---
{critique_json}
--- END CRITIQUE ---

Output your audit as a single JSON object following this schema:
{schema}

Be thorough and adversarial. If the critique is excellent, say so — but still look for any issues."""


_SYSTEM_AUDIT_RU = """Вы — состязательный мета-рецензент. Ваша задача — тщательно проверить литературную критику, составленную другой моделью ИИ.

ВАША МИССИЯ:
1. Проверить КАЖДОЕ фактическое утверждение критики на соответствие оригинальному тексту.
2. Выявить ГАЛЛЮЦИНАЦИИ: утверждения о тексте, которые просто не соответствуют действительности.
3. Обнаружить ПРОПУЩЕННЫЕ ПРОБЛЕМЫ, которые критика не заметила.
4. Отметить СЛАБЫЕ или РАСПЛЫВЧАТЫЕ пункты критики без конкретных доказательств.
5. Проверить, что процитированные фрагменты действительно есть в тексте (нет выдуманных цитат).
6. Оценить, справедливы ли оценки и согласуются ли они с найденными проблемами.
7. Дать оценку уверенности (0.0 = нет уверенности, 1.0 = полная уверенность в вашем аудите).
8. Выводите ТОЛЬКО валидный JSON. Без markdown-блоков кода, без пояснений за пределами JSON.
9. Весь ваш ответ должен быть ОДНИМ JSON-объектом. Начните с { и закончите }."""

_USER_AUDIT_RU = """Проведите аудит следующей литературной критики. Сравните её с оригинальным текстом.

--- ОРИГИНАЛЬНЫЙ ТЕКСТ ---
{text}
--- КОНЕЦ ОРИГИНАЛЬНОГО ТЕКСТА ---

--- КРИТИКА ДЛЯ АУДИТА ---
{critique_json}
--- КОНЕЦ КРИТИКИ ---

Выведите аудит в виде единого JSON-объекта по следующей схеме:
{schema}

Будьте тщательны и требовательны. Если критика отличная — скажите об этом, но всё равно ищите проблемы."""


# ── Public API ───────────────────────────────────────────────────────────

def build_primary_messages(
    text: str,
    language: str,
    deterministic: DeterministicAnalysis,
    requirements: str = "",
) -> list[dict[str, str]]:
    """Build the message list for the primary analyzer call."""
    is_ru = language == "ru"

    system = _SYSTEM_PRIMARY_RU if is_ru else _SYSTEM_PRIMARY_EN
    user_tpl = _USER_PRIMARY_RU if is_ru else _USER_PRIMARY_EN

    if requirements:
        if is_ru:
            req_block = f"--- ТРЕБОВАНИЯ АВТОРА ---\n{requirements}\n--- КОНЕЦ ТРЕБОВАНИЙ ---"
        else:
            req_block = f"--- AUTHOR REQUIREMENTS ---\n{requirements}\n--- END REQUIREMENTS ---"
    else:
        req_block = ""

    det_summary = _format_deterministic(deterministic, is_ru)

    user_msg = user_tpl.format(
        text=text,
        requirements_block=req_block,
        deterministic_summary=det_summary,
        schema=PRIMARY_OUTPUT_SCHEMA,
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]


def build_audit_messages(
    text: str,
    language: str,
    critique_json: str,
) -> list[dict[str, str]]:
    """Build the message list for the auditor call."""
    is_ru = language == "ru"

    system = _SYSTEM_AUDIT_RU if is_ru else _SYSTEM_AUDIT_EN
    user_tpl = _USER_AUDIT_RU if is_ru else _USER_AUDIT_EN

    user_msg = user_tpl.format(
        text=text,
        critique_json=critique_json,
        schema=AUDIT_OUTPUT_SCHEMA,
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]


def format_primary_prompt_for_display(
    text: str,
    language: str,
    deterministic: DeterministicAnalysis,
    requirements: str = "",
) -> str:
    """
    Format the primary analyzer prompt as a readable text block for inclusion in reports.
    Returns the full system + user prompt as it was sent to the LLM.
    """
    messages = build_primary_messages(text, language, deterministic, requirements)
    is_ru = language == "ru"
    
    lines = []
    if is_ru:
        lines.append("=== СИСТЕМНЫЙ ПРОМПТ ===\n")
    else:
        lines.append("=== SYSTEM PROMPT ===\n")
    
    lines.append(messages[0]["content"])
    lines.append("\n")
    
    if is_ru:
        lines.append("\n=== ПОЛЬЗОВАТЕЛЬСКИЙ ПРОМПТ ===\n")
    else:
        lines.append("\n=== USER PROMPT ===\n")
    
    lines.append(messages[1]["content"])
    
    return "\n".join(lines)


def _format_deterministic(det: DeterministicAnalysis, is_ru: bool) -> str:
    """Format deterministic analysis results for inclusion in prompts."""
    lines = []

    if is_ru:
        lines.append(f"Язык: {det.language} (уверенность: {det.language_confidence})")
        lines.append(f"Абзацев: {det.paragraph_count}, Предложений: {det.sentence_count}, Слов: {det.word_count}")
        lines.append(f"Символов: {det.char_count}")

        r = det.readability
        lines.append(f"\nЧитаемость:")
        lines.append(f"  Средняя длина предложения: {r.avg_sentence_length} слов")
        lines.append(f"  Длинных предложений (>25 слов): {r.long_sentence_count}")
        lines.append(f"  Очень длинных предложений (>40 слов): {r.very_long_sentence_count}")
        lines.append(f"  Богатство словаря: {r.vocabulary_richness}")
        if r.flesch_reading_ease is not None:
            lines.append(f"  Flesch Reading Ease: {r.flesch_reading_ease}")

        if det.repetitions:
            lines.append(f"\nПовторы (n-грамм):")
            for rep in det.repetitions[:10]:
                lines.append(f'  "{rep.phrase}" — {rep.count} раз (абз. {rep.locations})')

        if det.coreference_flags:
            lines.append(f"\nПотенциальные проблемы с местоимениями:")
            for cf in det.coreference_flags[:10]:
                lines.append(f"  [{cf.pronoun}] абз.{cf.paragraph_index}: {cf.issue}")

        if det.dangling_modifier_flags:
            lines.append(f"\nВозможные висячие модификаторы:")
            for dm in det.dangling_modifier_flags[:5]:
                lines.append(f"  абз.{dm.paragraph_index}: {dm.issue}")
    else:
        lines.append(f"Language: {det.language} (confidence: {det.language_confidence})")
        lines.append(f"Paragraphs: {det.paragraph_count}, Sentences: {det.sentence_count}, Words: {det.word_count}")
        lines.append(f"Characters: {det.char_count}")

        r = det.readability
        lines.append(f"\nReadability:")
        lines.append(f"  Average sentence length: {r.avg_sentence_length} words")
        lines.append(f"  Long sentences (>25 words): {r.long_sentence_count}")
        lines.append(f"  Very long sentences (>40 words): {r.very_long_sentence_count}")
        lines.append(f"  Vocabulary richness: {r.vocabulary_richness}")
        if r.flesch_reading_ease is not None:
            lines.append(f"  Flesch Reading Ease: {r.flesch_reading_ease}")

        if det.repetitions:
            lines.append(f"\nRepetitions (n-grams):")
            for rep in det.repetitions[:10]:
                lines.append(f'  "{rep.phrase}" — {rep.count} times (para. {rep.locations})')

        if det.coreference_flags:
            lines.append(f"\nPotential pronoun reference issues:")
            for cf in det.coreference_flags[:10]:
                lines.append(f"  [{cf.pronoun}] para.{cf.paragraph_index}: {cf.issue}")

        if det.dangling_modifier_flags:
            lines.append(f"\nPossible dangling modifiers:")
            for dm in det.dangling_modifier_flags[:5]:
                lines.append(f"  para.{dm.paragraph_index}: {dm.issue}")

    return "\n".join(lines)
