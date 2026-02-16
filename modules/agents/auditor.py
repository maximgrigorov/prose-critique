"""Auditor agent: cross-checks primary analysis using a second LLM."""

from __future__ import annotations

import json
import logging
from typing import Any

from modules.llm_client import LLMClient, extract_json
from modules.models import (
    AuditResult, AuditVerdict, AuditDisagreement, AuditMissedIssue,
    AuditHallucination, AuditWeakCritique, LLMCallMeta, Severity,
    PrimaryAnalysis,
)
from modules.utils.prompts import build_audit_messages

logger = logging.getLogger("prose-critique")


async def run_audit(
    client: LLMClient,
    text: str,
    language: str,
    primary_analysis: PrimaryAnalysis,
) -> tuple[AuditResult, LLMCallMeta]:
    """
    Run the auditor LLM to cross-check the primary analysis.
    Returns (audit_result, call_metadata).
    """
    logger.info("Running audit analysis (model: %s)...", client.config.audit.model)

    critique_json = primary_analysis.model_dump_json(indent=2)
    messages = build_audit_messages(text, language, critique_json)

    raw_response, meta = await client.chat(
        messages=messages,
        role="audit",
        prompt_id="audit_analysis",
        json_mode=True,
    )

    audit = _parse_audit_response(raw_response)
    call_meta = LLMCallMeta(**meta)

    logger.info(
        "Audit complete: verdict=%s, confidence=%.2f, %d disagreements, %d hallucinations",
        audit.audit_verdict.value,
        audit.confidence_score,
        len(audit.disagreements),
        len(audit.hallucinations),
    )

    return audit, call_meta


def _parse_audit_response(raw: str) -> AuditResult:
    """Parse the LLM JSON response into an AuditResult model."""
    cleaned = extract_json(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse audit JSON: %s", e)
        logger.debug("Raw response (first 2000 chars): %s", raw[:2000])
        return AuditResult(summary=f"[Parse error: {e}]")

    return _dict_to_audit(data)


def _dict_to_audit(d: dict[str, Any]) -> AuditResult:
    """Convert a dict to AuditResult, tolerating missing/extra fields."""
    result = AuditResult()

    result.audit_verdict = _safe_verdict(d.get("audit_verdict", "agree"))
    result.confidence_score = _safe_float(d.get("confidence_score", 0.0))

    for item in d.get("disagreements", []):
        result.disagreements.append(AuditDisagreement(
            claim=item.get("claim", ""),
            issue=item.get("issue", ""),
            evidence=item.get("evidence", ""),
            severity=_safe_severity(item.get("severity", "moderate")),
        ))

    for item in d.get("missed_issues", []):
        result.missed_issues.append(AuditMissedIssue(
            description=item.get("description", ""),
            evidence=item.get("evidence", ""),
            severity=_safe_severity(item.get("severity", "moderate")),
        ))

    for item in d.get("hallucinations", []):
        result.hallucinations.append(AuditHallucination(
            claim=item.get("claim", ""),
            why_hallucinated=item.get("why_hallucinated", ""),
        ))

    for item in d.get("weak_critiques", []):
        result.weak_critiques.append(AuditWeakCritique(
            claim=item.get("claim", ""),
            why_weak=item.get("why_weak", ""),
        ))

    result.summary = d.get("summary", "")
    return result


def _safe_float(v: Any) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def _safe_verdict(v: Any) -> AuditVerdict:
    try:
        return AuditVerdict(v)
    except (ValueError, KeyError):
        return AuditVerdict.agree


def _safe_severity(v: Any) -> Severity:
    try:
        return Severity(v)
    except (ValueError, KeyError):
        return Severity.moderate
