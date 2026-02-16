"""Contract tests for data models (no API keys needed)."""

import json

import pytest

from modules.models import (
    CritiqueReport, PrimaryAnalysis, AuditResult, DeterministicAnalysis,
    TextOverview, QualityScores, LocalIssue, GlobalIssue, Severity,
    GlobalIssueCategory, ReaderQuestion, ReaderQuestionType,
    AuditVerdict, AuditDisagreement, LLMCallMeta,
    RepetitionItem, ReadabilityMetrics, CoreferenceFlag,
)


class TestDeterministicAnalysis:
    def test_defaults(self):
        da = DeterministicAnalysis()
        assert da.language == "en"
        assert da.paragraph_count == 0
        assert da.repetitions == []

    def test_serialization(self):
        da = DeterministicAnalysis(
            language="ru",
            language_confidence=0.95,
            paragraph_count=3,
            sentence_count=10,
            word_count=100,
            char_count=500,
            repetitions=[
                RepetitionItem(phrase="big red", count=4, locations=[0, 1, 2, 3])
            ],
        )
        data = json.loads(da.model_dump_json())
        assert data["language"] == "ru"
        assert len(data["repetitions"]) == 1
        assert data["repetitions"][0]["count"] == 4


class TestPrimaryAnalysis:
    def test_defaults(self):
        pa = PrimaryAnalysis()
        assert pa.local_issues == []
        assert pa.quality_scores.overall == 0.0

    def test_full_construction(self):
        pa = PrimaryAnalysis(
            text_overview=TextOverview(genre_guess="fiction", tone="reflective"),
            local_issues=[
                LocalIssue(
                    paragraph_index=0,
                    sentence="He walked in.",
                    issue_type="style",
                    severity=Severity.minor,
                    description="Flat opening.",
                    suggestion="Add sensory detail.",
                )
            ],
            global_issues=[
                GlobalIssue(
                    category=GlobalIssueCategory.pacing,
                    severity=Severity.moderate,
                    description="Slow middle section.",
                )
            ],
            quality_scores=QualityScores(
                clarity=7.0, conciseness=6.0, vividness=5.0,
                originality=4.0, coherence=8.0, engagement=6.0, overall=6.0,
            ),
            reader_questions=[
                ReaderQuestion(
                    question="Who is 'he'?",
                    location="paragraph 0",
                    type=ReaderQuestionType.unclear_reference,
                )
            ],
            strengths=["Strong ending."],
            summary="Decent prose with room for improvement.",
        )
        data = json.loads(pa.model_dump_json())
        assert len(data["local_issues"]) == 1
        assert data["quality_scores"]["overall"] == 6.0
        assert len(data["reader_questions"]) == 1


class TestAuditResult:
    def test_defaults(self):
        ar = AuditResult()
        assert ar.audit_verdict == AuditVerdict.agree
        assert ar.confidence_score == 0.0

    def test_full_construction(self):
        ar = AuditResult(
            audit_verdict=AuditVerdict.mostly_agree,
            confidence_score=0.85,
            disagreements=[
                AuditDisagreement(
                    claim="Grammar is poor",
                    issue="Grammar is actually acceptable",
                    evidence="'He walked in quietly.'",
                    severity=Severity.minor,
                )
            ],
            summary="Primary critique is mostly accurate.",
        )
        data = json.loads(ar.model_dump_json())
        assert data["audit_verdict"] == "mostly_agree"
        assert len(data["disagreements"]) == 1


class TestCritiqueReport:
    def test_minimal(self):
        report = CritiqueReport()
        data = json.loads(report.model_dump_json())
        assert data["version"] == "1.0.0"
        assert data["audit"] is None
        assert data["llm_calls"] == []

    def test_full_roundtrip(self):
        report = CritiqueReport(
            version="1.0.0",
            input_text_hash="abc123",
            input_char_count=500,
            requirements="be concise",
            language="en",
            deterministic=DeterministicAnalysis(language="en", paragraph_count=3),
            primary_analysis=PrimaryAnalysis(
                summary="Good text.",
                quality_scores=QualityScores(overall=7.5),
            ),
            audit=AuditResult(
                audit_verdict=AuditVerdict.agree,
                confidence_score=0.9,
            ),
            llm_calls=[
                LLMCallMeta(
                    call_id="test_1",
                    model="gpt-4o",
                    prompt_id="primary",
                    input_tokens=100,
                    output_tokens=200,
                    duration_ms=1500.0,
                )
            ],
            timestamp="2025-01-01T00:00:00Z",
            duration_ms=3000.0,
        )

        json_str = report.model_dump_json()
        data = json.loads(json_str)

        reconstructed = CritiqueReport(**data)
        assert reconstructed.version == "1.0.0"
        assert reconstructed.primary_analysis.quality_scores.overall == 7.5
        assert reconstructed.audit.audit_verdict == AuditVerdict.agree
        assert len(reconstructed.llm_calls) == 1


class TestLLMCallMeta:
    def test_construction(self):
        meta = LLMCallMeta(
            call_id="test",
            model="gpt-4o",
            prompt_id="primary_analysis",
            input_tokens=500,
            output_tokens=1000,
            duration_ms=2500.0,
            cached=False,
        )
        assert meta.model == "gpt-4o"
        assert meta.cached is False
