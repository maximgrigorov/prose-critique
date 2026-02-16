"""Report builder: generates Markdown and JSON reports from analysis results."""

from __future__ import annotations

import json
import logging
from typing import Optional

from modules.models import (
    CritiqueReport, PrimaryAnalysis, AuditResult, DeterministicAnalysis,
    Severity,
)
from modules.utils.language import language_name

logger = logging.getLogger("prose-critique")


def build_markdown_report(report: CritiqueReport) -> str:
    """Generate a human-readable Markdown report."""
    lang = report.language
    is_ru = lang == "ru"
    lines: list[str] = []

    _h = lambda level, text: "#" * level + " " + text

    if is_ru:
        lines.append(_h(1, "Критический разбор прозы"))
        lines.append("")
        lines.append(f"**Язык:** {language_name(lang)}  ")
        lines.append(f"**Символов:** {report.input_char_count}  ")
        lines.append(f"**Дата:** {report.timestamp}  ")
        if report.requirements:
            lines.append(f"**Требования:** {report.requirements}  ")
    else:
        lines.append(_h(1, "Prose Critique Report"))
        lines.append("")
        lines.append(f"**Language:** {language_name(lang)}  ")
        lines.append(f"**Characters:** {report.input_char_count}  ")
        lines.append(f"**Date:** {report.timestamp}  ")
        if report.requirements:
            lines.append(f"**Requirements:** {report.requirements}  ")

    lines.append("")

    # ── Input text ────────────────────────────────────────────────────
    if report.input_text:
        lines.append(_h(2, "Исходный текст" if is_ru else "Input Text"))
        lines.append("")
        lines.append("```")
        lines.append(report.input_text)
        lines.append("```")
        lines.append("")

    # ── Text overview ─────────────────────────────────────────────────
    pa = report.primary_analysis
    ov = pa.text_overview

    lines.append(_h(2, "Обзор текста" if is_ru else "Text Overview"))
    lines.append("")
    if is_ru:
        lines.append(f"- **Жанр:** {ov.genre_guess}")
        lines.append(f"- **Тон:** {ov.tone}")
        lines.append(f"- **Аудитория:** {ov.apparent_audience}")
        lines.append(f"- **Слов:** {ov.word_count}, **Абзацев:** {ov.paragraph_count}")
    else:
        lines.append(f"- **Genre:** {ov.genre_guess}")
        lines.append(f"- **Tone:** {ov.tone}")
        lines.append(f"- **Audience:** {ov.apparent_audience}")
        lines.append(f"- **Words:** {ov.word_count}, **Paragraphs:** {ov.paragraph_count}")
    lines.append("")

    # ── Quality scores ────────────────────────────────────────────────
    qs = pa.quality_scores
    lines.append(_h(2, "Оценки качества" if is_ru else "Quality Scores"))
    lines.append("")
    score_labels = {
        "clarity": ("Ясность", "Clarity"),
        "conciseness": ("Лаконичность", "Conciseness"),
        "vividness": ("Яркость", "Vividness"),
        "originality": ("Оригинальность", "Originality"),
        "coherence": ("Связность", "Coherence"),
        "engagement": ("Вовлечённость", "Engagement"),
        "overall": ("Общая оценка", "Overall"),
    }
    for field, (ru_label, en_label) in score_labels.items():
        val = getattr(qs, field)
        bar = _score_bar(val)
        label = ru_label if is_ru else en_label
        lines.append(f"| {label} | {bar} {val:.1f}/10 |")
    lines.append("")

    # ── Structural outline ────────────────────────────────────────────
    if pa.structural_outline:
        lines.append(_h(2, "Структура текста" if is_ru else "Structural Outline"))
        lines.append("")
        for item in pa.structural_outline:
            p_label = "Абз." if is_ru else "Para."
            lines.append(f"**{p_label} {item.paragraph_index}** — *{item.intent}*  ")
            lines.append(f"{item.summary}  ")
            lines.append("")

    # ── Local issues ──────────────────────────────────────────────────
    if pa.local_issues:
        lines.append(_h(2, "Локальные проблемы" if is_ru else "Local Issues"))
        lines.append("")
        for i, issue in enumerate(pa.local_issues, 1):
            sev_icon = _severity_icon(issue.severity)
            lines.append(f"{sev_icon} **#{i}** [{issue.issue_type}] — "
                         f"{'Абз.' if is_ru else 'Para.'} {issue.paragraph_index}")
            if issue.sentence:
                lines.append(f"> {issue.sentence[:200]}")
            lines.append(f"  {issue.description}")
            if issue.suggestion:
                suggestion_label = "Рекомендация" if is_ru else "Suggestion"
                lines.append(f"  *{suggestion_label}:* {issue.suggestion}")
            lines.append("")

    # ── Global issues ─────────────────────────────────────────────────
    if pa.global_issues:
        lines.append(_h(2, "Глобальные проблемы" if is_ru else "Global Issues"))
        lines.append("")
        for i, issue in enumerate(pa.global_issues, 1):
            sev_icon = _severity_icon(issue.severity)
            lines.append(f"{sev_icon} **#{i}** [{issue.category.value}]")
            lines.append(f"  {issue.description}")
            if issue.evidence:
                lines.append(f"  > {issue.evidence[:200]}")
            lines.append("")

    # ── Cliché detection ──────────────────────────────────────────────
    if pa.cliche_detection:
        lines.append(_h(2, "Обнаруженные клише" if is_ru else "Cliché Detection"))
        lines.append("")
        for cl in pa.cliche_detection:
            lines.append(f"- **\"{cl.phrase}\"** ({cl.location})")
            if cl.suggestion:
                lines.append(f"  {cl.suggestion}")
        lines.append("")

    # ── Reader questions ──────────────────────────────────────────────
    if pa.reader_questions:
        lines.append(_h(2, "Вопросы читателя" if is_ru else "Reader Questions"))
        lines.append("")
        for rq in pa.reader_questions:
            lines.append(f"- **{rq.question}** ({rq.location}) [{rq.type.value}]")
        lines.append("")

    # ── Strengths ─────────────────────────────────────────────────────
    if pa.strengths:
        lines.append(_h(2, "Сильные стороны" if is_ru else "Strengths"))
        lines.append("")
        for s in pa.strengths:
            lines.append(f"- {s}")
        lines.append("")

    # ── Improvement suggestions ───────────────────────────────────────
    if pa.improvement_suggestions:
        lines.append(_h(2, "Рекомендации по улучшению" if is_ru else "Improvement Suggestions"))
        lines.append("")
        for sug in pa.improvement_suggestions:
            prio = _severity_icon(sug.priority)
            lines.append(f"{prio} **[{sug.category}]** {sug.suggestion}")
        lines.append("")

    # ── Summary ───────────────────────────────────────────────────────
    if pa.summary:
        lines.append(_h(2, "Итоговое заключение" if is_ru else "Summary"))
        lines.append("")
        lines.append(pa.summary)
        lines.append("")

    # ── Deterministic pre-analysis ────────────────────────────────────
    det = report.deterministic
    lines.append(_h(2, "Детерминированный анализ" if is_ru else "Deterministic Pre-Analysis"))
    lines.append("")
    r = det.readability
    if is_ru:
        lines.append(f"- **Средняя длина предложения:** {r.avg_sentence_length} слов")
        lines.append(f"- **Длинных предложений (>25):** {r.long_sentence_count}")
        lines.append(f"- **Богатство словаря:** {r.vocabulary_richness:.4f}")
    else:
        lines.append(f"- **Avg sentence length:** {r.avg_sentence_length} words")
        lines.append(f"- **Long sentences (>25):** {r.long_sentence_count}")
        lines.append(f"- **Vocabulary richness:** {r.vocabulary_richness:.4f}")
        if r.flesch_reading_ease is not None:
            lines.append(f"- **Flesch Reading Ease:** {r.flesch_reading_ease}")
    lines.append("")

    if det.repetitions:
        lines.append(_h(3, "Повторы" if is_ru else "Repetitions"))
        lines.append("")
        for rep in det.repetitions[:10]:
            lines.append(f"- \"{rep.phrase}\" x{rep.count}")
        lines.append("")

    # ── Audit section ─────────────────────────────────────────────────
    if report.audit:
        a = report.audit
        lines.append(_h(2, "Аудит критики" if is_ru else "Audit of Critique"))
        lines.append("")
        
        # Verdict with explanation
        verdict_explanations = {
            "agree": {
                "ru": "**Согласен** — Аудитор согласен с оценкой. Критика точна и обоснована.",
                "en": "**Agree** — The auditor agrees with the assessment. Critique is accurate and well-founded."
            },
            "mostly_agree": {
                "ru": "**В основном согласен** — Критика в целом верна, но есть мелкие замечания.",
                "en": "**Mostly Agree** — The critique is generally correct, but has minor issues."
            },
            "mixed": {
                "ru": "**Смешанно** — Критика частично верна. Есть и точные наблюдения, и проблемные утверждения.",
                "en": "**Mixed** — The critique is partially correct. Contains both accurate observations and problematic claims."
            },
            "mostly_disagree": {
                "ru": "**В основном не согласен** — Большая часть критики проблемна или необоснованна.",
                "en": "**Mostly Disagree** — Most of the critique is problematic or unfounded."
            },
            "disagree": {
                "ru": "**Не согласен** — Критика неточна, содержит галлюцинации или пропускает ключевые моменты.",
                "en": "**Disagree** — The critique is inaccurate, contains hallucinations, or misses key points."
            }
        }
        
        verdict_text = verdict_explanations.get(a.audit_verdict.value, {}).get("ru" if is_ru else "en", a.audit_verdict.value)
        lines.append(f"**Вердикт:** {verdict_text}" if is_ru else f"**Verdict:** {verdict_text}")
        lines.append("")
        
        # Confidence with scale explanation
        c_label = "Уверенность аудитора" if is_ru else "Auditor Confidence"
        scale_label = "шкала 0.0–1.0, где 1.0 = полная уверенность" if is_ru else "scale 0.0–1.0, where 1.0 = full confidence"
        lines.append(f"**{c_label}:** {a.confidence_score:.2f} ({scale_label})")
        lines.append("")

        if a.disagreements:
            lines.append(_h(3, "Разногласия" if is_ru else "Disagreements"))
            lines.append("")
            for dis in a.disagreements:
                sev_icon = _severity_icon(dis.severity)
                lines.append(f"{sev_icon} **{dis.claim}**")
                lines.append(f"  {dis.issue}")
                if dis.evidence:
                    lines.append(f"  > {dis.evidence[:200]}")
                lines.append("")

        if a.hallucinations:
            lines.append(_h(3, "Галлюцинации" if is_ru else "Hallucinations"))
            lines.append("")
            for h in a.hallucinations:
                lines.append(f"- **{h.claim}**: {h.why_hallucinated}")
            lines.append("")

        if a.missed_issues:
            lines.append(_h(3, "Пропущенные проблемы" if is_ru else "Missed Issues"))
            lines.append("")
            for mi in a.missed_issues:
                lines.append(f"- {mi.description}")
                if mi.evidence:
                    lines.append(f"  > {mi.evidence[:200]}")
            lines.append("")

        if a.weak_critiques:
            lines.append(_h(3, "Слабые пункты критики" if is_ru else "Weak Critique Points"))
            lines.append("")
            for wc in a.weak_critiques:
                lines.append(f"- **{wc.claim}**: {wc.why_weak}")
            lines.append("")

        if a.summary:
            lines.append(_h(3, "Резюме аудита" if is_ru else "Audit Summary"))
            lines.append("")
            lines.append(a.summary)
            lines.append("")

    # ── Generated prompt ──────────────────────────────────────────────
    if report.generated_prompt:
        lines.append(_h(2, "Сгенерированный промпт" if is_ru else "Generated Prompt"))
        lines.append("")
        if is_ru:
            lines.append("Полный промпт, отправленный LLM-анализатору (система + пользователь):")
        else:
            lines.append("Full prompt sent to the LLM analyzer (system + user):")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Показать промпт / Show prompt</summary>" if is_ru else "<summary>Show prompt</summary>")
        lines.append("")
        lines.append("```")
        lines.append(report.generated_prompt)
        lines.append("```")
        lines.append("</details>")
        lines.append("")

    # ── LLM calls metadata ────────────────────────────────────────────
    if report.llm_calls:
        lines.append(_h(2, "Метаданные вызовов LLM" if is_ru else "LLM Calls Metadata"))
        lines.append("")
        header = "| Call ID | Model | Tokens In | Tokens Out | Duration (ms) | Cached |"
        sep = "|---------|-------|-----------|------------|---------------|--------|"
        lines.append(header)
        lines.append(sep)
        for c in report.llm_calls:
            lines.append(
                f"| {c.call_id} | {c.model} | "
                f"{c.input_tokens or '-'} | {c.output_tokens or '-'} | "
                f"{c.duration_ms or '-'} | {'Yes' if c.cached else 'No'} |"
            )
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated by prose-critique v{report.version}*")

    return "\n".join(lines)


def build_json_report(report: CritiqueReport) -> str:
    """Serialize the full report to JSON."""
    return report.model_dump_json(indent=2)


def _score_bar(score: float, max_score: float = 10.0, bar_length: int = 10) -> str:
    """Generate a simple text-based score bar."""
    filled = round(score / max_score * bar_length)
    return "[" + "=" * filled + "-" * (bar_length - filled) + "]"


def _severity_icon(sev: Severity) -> str:
    icons = {
        Severity.minor: "[.]",
        Severity.moderate: "[!]",
        Severity.major: "[!!]",
        Severity.critical: "[!!!]",
    }
    return icons.get(sev, "[?]")
