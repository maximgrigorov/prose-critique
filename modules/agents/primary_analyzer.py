"""Primary LLM-based prose analyzer agent."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from modules.llm_client import LLMClient, extract_json
from modules.models import (
    PrimaryAnalysis, DeterministicAnalysis, LLMCallMeta,
    TextOverview, StructuralOutlineItem, LocalIssue, GlobalIssue,
    QualityScores, ClicheItem, ReaderQuestion, ImprovementSuggestion,
    Severity, GlobalIssueCategory, ReaderQuestionType,
)
from modules.utils.prompts import build_primary_messages

logger = logging.getLogger("prose-critique")


async def run_primary_analysis(
    client: LLMClient,
    text: str,
    language: str,
    deterministic: DeterministicAnalysis,
    requirements: str = "",
) -> tuple[PrimaryAnalysis, LLMCallMeta]:
    """
    Run the primary LLM analysis.
    Returns (analysis, call_metadata).
    """
    logger.info("Running primary LLM analysis (model: %s)...", client.config.primary.model)

    messages = build_primary_messages(text, language, deterministic, requirements)

    raw_response, meta = await client.chat(
        messages=messages,
        role="primary",
        prompt_id="primary_analysis",
        json_mode=True,
    )

    analysis = _parse_primary_response(raw_response)
    call_meta = LLMCallMeta(**meta)

    n_issues = len(analysis.local_issues) + len(analysis.global_issues)
    if n_issues == 0 and analysis.quality_scores.overall == 0.0 and not analysis.summary:
        logger.warning(
            "Primary analysis returned empty results. Model may have produced "
            "unparseable output. Raw response length: %d chars", len(raw_response)
        )
        logger.warning("Raw response first 1000 chars: %s", raw_response[:1000])

    logger.info(
        "Primary analysis complete: %d local issues, %d global issues, "
        "%d reader questions, overall=%.1f",
        len(analysis.local_issues),
        len(analysis.global_issues),
        len(analysis.reader_questions),
        analysis.quality_scores.overall,
    )

    return analysis, call_meta


def _parse_primary_response(raw: str) -> PrimaryAnalysis:
    """Parse the LLM JSON response into a PrimaryAnalysis model."""
    # Try extracting JSON in case it's wrapped
    cleaned = extract_json(raw)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse primary analysis JSON: %s", e)
        logger.error("Cleaned response (first 2000 chars): %s", cleaned[:2000])
        logger.debug("Full raw response (first 5000 chars): %s", raw[:5000])
        return PrimaryAnalysis(
            summary=f"[JSON parse error: {e}]. The model response could not be parsed."
        )

    # Handle case where the data might be nested under a key
    if isinstance(data, dict):
        # Some models wrap response in {"response": {...}} or {"result": {...}}
        if len(data) == 1:
            key = next(iter(data))
            inner = data[key]
            if isinstance(inner, dict) and ("text_overview" in inner or "quality_scores" in inner
                                            or "local_issues" in inner):
                logger.debug("Unwrapping nested response from key '%s'", key)
                data = inner

    return _dict_to_primary(data)


def _dict_to_primary(d: dict[str, Any]) -> PrimaryAnalysis:
    """Convert a dict to PrimaryAnalysis, tolerating missing/extra fields."""
    analysis = PrimaryAnalysis()

    ov = d.get("text_overview", {})
    if ov:
        analysis.text_overview = TextOverview(
            genre_guess=ov.get("genre_guess", ""),
            tone=ov.get("tone", ""),
            apparent_audience=ov.get("apparent_audience", ""),
            language=ov.get("language", ""),
            word_count=_safe_int(ov.get("word_count", 0)),
            paragraph_count=_safe_int(ov.get("paragraph_count", 0)),
        )

    for item in d.get("structural_outline", []):
        analysis.structural_outline.append(StructuralOutlineItem(
            paragraph_index=_safe_int(item.get("paragraph_index", 0)),
            intent=item.get("intent", ""),
            summary=item.get("summary", ""),
        ))

    for item in d.get("local_issues", []):
        analysis.local_issues.append(LocalIssue(
            paragraph_index=_safe_int(item.get("paragraph_index", 0)),
            sentence=item.get("sentence", ""),
            issue_type=item.get("issue_type", ""),
            severity=_safe_enum(item.get("severity", "minor"), Severity, Severity.minor),
            description=item.get("description", ""),
            suggestion=item.get("suggestion", ""),
        ))

    for item in d.get("global_issues", []):
        analysis.global_issues.append(GlobalIssue(
            category=_safe_enum(item.get("category", "other"), GlobalIssueCategory, GlobalIssueCategory.other),
            severity=_safe_enum(item.get("severity", "minor"), Severity, Severity.minor),
            description=item.get("description", ""),
            evidence=item.get("evidence", ""),
        ))

    qs = d.get("quality_scores", {})
    if qs:
        analysis.quality_scores = QualityScores(
            clarity=_safe_float(qs.get("clarity", 0)),
            conciseness=_safe_float(qs.get("conciseness", 0)),
            vividness=_safe_float(qs.get("vividness", 0)),
            originality=_safe_float(qs.get("originality", 0)),
            coherence=_safe_float(qs.get("coherence", 0)),
            engagement=_safe_float(qs.get("engagement", 0)),
            overall=_safe_float(qs.get("overall", 0)),
        )

    for item in d.get("cliche_detection", []):
        analysis.cliche_detection.append(ClicheItem(
            phrase=item.get("phrase", ""),
            location=item.get("location", ""),
            suggestion=item.get("suggestion", ""),
        ))

    for item in d.get("reader_questions", []):
        analysis.reader_questions.append(ReaderQuestion(
            question=item.get("question", ""),
            location=item.get("location", ""),
            type=_safe_enum(item.get("type", "unclear_reference"), ReaderQuestionType, ReaderQuestionType.unclear_reference),
        ))

    for item in d.get("improvement_suggestions", []):
        analysis.improvement_suggestions.append(ImprovementSuggestion(
            category=item.get("category", ""),
            suggestion=item.get("suggestion", ""),
            priority=_safe_enum(item.get("priority", "moderate"), Severity, Severity.moderate),
        ))

    analysis.strengths = d.get("strengths", [])
    analysis.summary = d.get("summary", "")

    return analysis


def _safe_int(v: Any) -> int:
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def _safe_float(v: Any) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def _safe_enum(v: Any, enum_cls: type, default: Any) -> Any:
    try:
        return enum_cls(v)
    except (ValueError, KeyError):
        return default
