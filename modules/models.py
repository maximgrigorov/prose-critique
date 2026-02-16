"""Pydantic data models for prose-critique pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────

class Severity(str, Enum):
    minor = "minor"
    moderate = "moderate"
    major = "major"
    critical = "critical"


class GlobalIssueCategory(str, Enum):
    logic = "logic"
    pacing = "pacing"
    voice = "voice"
    pov_consistency = "pov_consistency"
    character_consistency = "character_consistency"
    contradictions = "contradictions"
    tone = "tone"
    other = "other"


class ReaderQuestionType(str, Enum):
    unclear_reference = "unclear_reference"
    missing_antecedent = "missing_antecedent"
    undefined_term = "undefined_term"
    logical_gap = "logical_gap"


class AuditVerdict(str, Enum):
    agree = "agree"
    mostly_agree = "mostly_agree"
    mixed = "mixed"
    mostly_disagree = "mostly_disagree"
    disagree = "disagree"


# ── Deterministic analysis models ────────────────────────────────────────

class RepetitionItem(BaseModel):
    phrase: str
    count: int
    locations: list[int] = Field(default_factory=list, description="Paragraph indices")


class ReadabilityMetrics(BaseModel):
    avg_sentence_length: float = 0.0
    avg_word_length: float = 0.0
    long_sentence_count: int = 0
    very_long_sentence_count: int = 0
    vocabulary_richness: float = 0.0
    flesch_reading_ease: Optional[float] = None


class CoreferenceFlag(BaseModel):
    pronoun: str
    paragraph_index: int
    sentence_index: int
    context: str
    issue: str


class DanglingModifierFlag(BaseModel):
    modifier: str
    paragraph_index: int
    sentence: str
    issue: str


class DeterministicAnalysis(BaseModel):
    language: str = "en"
    language_confidence: float = 0.0
    paragraph_count: int = 0
    sentence_count: int = 0
    word_count: int = 0
    char_count: int = 0
    paragraphs: list[str] = Field(default_factory=list)
    repetitions: list[RepetitionItem] = Field(default_factory=list)
    readability: ReadabilityMetrics = Field(default_factory=ReadabilityMetrics)
    coreference_flags: list[CoreferenceFlag] = Field(default_factory=list)
    dangling_modifier_flags: list[DanglingModifierFlag] = Field(default_factory=list)


# ── Primary analysis models ─────────────────────────────────────────────

class TextOverview(BaseModel):
    genre_guess: str = ""
    tone: str = ""
    apparent_audience: str = ""
    language: str = ""
    word_count: int = 0
    paragraph_count: int = 0


class StructuralOutlineItem(BaseModel):
    paragraph_index: int
    intent: str = ""
    summary: str = ""


class LocalIssue(BaseModel):
    paragraph_index: int
    sentence: str = ""
    issue_type: str = ""
    severity: Severity = Severity.minor
    description: str = ""
    suggestion: str = ""


class GlobalIssue(BaseModel):
    category: GlobalIssueCategory = GlobalIssueCategory.other
    severity: Severity = Severity.minor
    description: str = ""
    evidence: str = ""


class QualityScores(BaseModel):
    clarity: float = 0.0
    conciseness: float = 0.0
    vividness: float = 0.0
    originality: float = 0.0
    coherence: float = 0.0
    engagement: float = 0.0
    overall: float = 0.0


class ClicheItem(BaseModel):
    phrase: str = ""
    location: str = ""
    suggestion: str = ""


class ReaderQuestion(BaseModel):
    question: str = ""
    location: str = ""
    type: ReaderQuestionType = ReaderQuestionType.unclear_reference


class ImprovementSuggestion(BaseModel):
    category: str = ""
    suggestion: str = ""
    priority: Severity = Severity.moderate


class PrimaryAnalysis(BaseModel):
    text_overview: TextOverview = Field(default_factory=TextOverview)
    structural_outline: list[StructuralOutlineItem] = Field(default_factory=list)
    local_issues: list[LocalIssue] = Field(default_factory=list)
    global_issues: list[GlobalIssue] = Field(default_factory=list)
    quality_scores: QualityScores = Field(default_factory=QualityScores)
    cliche_detection: list[ClicheItem] = Field(default_factory=list)
    reader_questions: list[ReaderQuestion] = Field(default_factory=list)
    improvement_suggestions: list[ImprovementSuggestion] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    summary: str = ""


# ── Audit models ─────────────────────────────────────────────────────────

class AuditDisagreement(BaseModel):
    claim: str = ""
    issue: str = ""
    evidence: str = ""
    severity: Severity = Severity.moderate


class AuditMissedIssue(BaseModel):
    description: str = ""
    evidence: str = ""
    severity: Severity = Severity.moderate


class AuditHallucination(BaseModel):
    claim: str = ""
    why_hallucinated: str = ""


class AuditWeakCritique(BaseModel):
    claim: str = ""
    why_weak: str = ""


class AuditResult(BaseModel):
    audit_verdict: AuditVerdict = AuditVerdict.agree
    confidence_score: float = 0.0
    disagreements: list[AuditDisagreement] = Field(default_factory=list)
    missed_issues: list[AuditMissedIssue] = Field(default_factory=list)
    hallucinations: list[AuditHallucination] = Field(default_factory=list)
    weak_critiques: list[AuditWeakCritique] = Field(default_factory=list)
    summary: str = ""


# ── LLM call metadata ───────────────────────────────────────────────────

class LLMCallMeta(BaseModel):
    call_id: str = ""
    model: str = ""
    prompt_id: str = ""
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    duration_ms: Optional[float] = None
    cached: bool = False


# ── Full report ──────────────────────────────────────────────────────────

class CritiqueReport(BaseModel):
    version: str = "1.0.0"
    input_text_hash: str = ""
    input_char_count: int = 0
    input_text: str = ""
    requirements: str = ""
    generated_prompt: str = ""
    language: str = "en"
    deterministic: DeterministicAnalysis = Field(default_factory=DeterministicAnalysis)
    primary_analysis: PrimaryAnalysis = Field(default_factory=PrimaryAnalysis)
    audit: Optional[AuditResult] = None
    llm_calls: list[LLMCallMeta] = Field(default_factory=list)
    timestamp: str = ""
    duration_ms: float = 0.0
