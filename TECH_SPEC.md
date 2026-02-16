# Technical Specification: Prose Critique

## 1. Overview

Prose Critique is a local-first, open-source Python application that produces detailed analytical critique reports for prose text. It is inspired by the architecture of [lyrics-enhancer](https://github.com/maximgrigorov/lyrics-enhancer) but adapted for prose analysis rather than lyric rewriting.

**Core principles:**
- One-pass analysis only (no rewriting/refinement loop)
- Deterministic checks where possible (no LLM for language detection, segmentation, etc.)
- Structured output (Markdown + JSON)
- Optional two-model cross-check for critique quality assurance
- Local-first: no external DB, all data in filesystem

## 2. Architecture

### 2.1 Pipeline

The system runs a linear pipeline:

1. **Input Validation** — enforce 8192-char hard cap, reject empty input
2. **Deterministic Pre-Analysis** — all local computation, no LLM:
   - Language detection (langdetect + Cyrillic ratio check)
   - Paragraph segmentation (double-newline splitting)
   - Sentence segmentation (razdel for Russian, regex fallback for English)
   - Word counting (razdel-aware tokenization)
   - Readability metrics (Flesch Reading Ease for EN, sentence/word stats)
   - N-gram repetition detection (bigrams, trigrams)
   - Single-word repetition detection
   - Coreference flag heuristics (pronouns without antecedents, excluding capitalized pronouns)
   - Dangling modifier heuristics (pattern matching)
3. **Auto-Requirements Generation** (if no user requirements provided):
   - 15 baseline criteria (universal prose quality standards)
   - Conditional criteria based on deterministic findings (long sentences, low vocabulary, etc.)
   - Text-type detection: fairy-tale/fantasy, dialogue, children's literature, archaic language
   - All in the detected language (Russian or English)
4. **Primary LLM Analysis** — async call to primary model:
   - Text overview (genre, tone, audience)
   - Structural outline (per-paragraph intent/summary)
   - Local issues (per-paragraph, per-sentence)
   - Global issues (logic, pacing, voice, POV, consistency)
   - Quality scores (7 dimensions, 0-10 scale)
   - Cliché detection
   - Reader questions (unclear references, missing antecedents)
   - Improvement suggestions (bullet points, not rewrites)
   - Strengths
5. **Audit LLM Analysis** (optional) — async call to audit model:
   - Verifies primary critique claims against original text
   - Detects hallucinations (fabricated quotes, incorrect claims)
   - Identifies missed issues
   - Flags weak/vague critique points
   - Produces verdict with confidence score and human-readable explanation
6. **Report Generation** — produces both Markdown and JSON outputs:
   - Includes original input text
   - Includes generated prompt (system + user messages)
   - Includes audit verdict with scale explanation
   - Supports Print and PDF export (A4 format) via web UI

### 2.2 Module Structure

```
modules/
  config.py         — Dataclass-based config with JSON + .env loading
  models.py         — Pydantic v2 models for all data structures
  logger.py         — Per-run file logging, secret redaction
  llm_client.py     — Async OpenAI client with retry, caching, LiteLLM support, JSON extraction
  orchestrator.py   — Pipeline coordination, progress callbacks, auto-requirements integration
  agents/
    deterministic_analyzers.py — All local analysis
    primary_analyzer.py        — Primary LLM agent with robust JSON parsing
    auditor.py                 — Audit LLM agent with JSON extraction
    report_builder.py          — MD + JSON report generation with input text and prompt inclusion
  utils/
    language.py     — Language detection wrapper with Cyrillic ratio check
    segmentation.py — Paragraph/sentence splitting (razdel for Russian, regex fallback)
    heuristics.py   — Repetition, readability, coreference, dangling modifiers
    prompts.py      — Dynamic prompt generation (EN/RU), prompt formatting for display
    auto_requirements.py — Auto-generate baseline + conditional + text-type requirements
```

### 2.3 Key Design Decisions

**Why one-pass?** Prose critique does not benefit from iterative refinement the way lyric rewriting does. A single thorough analysis is sufficient, and multiple passes would increase cost without proportional quality gain.

**Why two models?** The primary model can hallucinate or produce vague critique. An independent audit model serves as a quality gate, similar to code review.

**Why deterministic pre-analysis?** Language detection, readability metrics, and repetition detection are reliably handled by algorithms. Using an LLM for these would add cost and latency without benefit. The pre-analysis results are also fed to the LLM prompt to ground its analysis.

**Why async?** LLM calls are I/O-bound and can take 10-60 seconds. Async allows the web UI to remain responsive.

## 3. Data Models

All data models use Pydantic v2 for validation and serialization.

### 3.1 CritiqueReport (top-level)

```python
class CritiqueReport(BaseModel):
    version: str
    input_text_hash: str
    input_text: str
    requirements: str
    generated_prompt: str
    input_char_count: int
    requirements: str
    language: str
    deterministic: DeterministicAnalysis
    primary_analysis: PrimaryAnalysis
    audit: Optional[AuditResult]
    llm_calls: list[LLMCallMeta]
    timestamp: str
    duration_ms: float
```

### 3.2 DeterministicAnalysis

Contains: language, confidence, paragraph/sentence/word/char counts, paragraph texts, repetitions, readability metrics, coreference flags, dangling modifier flags.

### 3.3 PrimaryAnalysis

Contains: text overview, structural outline, local issues (per-paragraph), global issues, quality scores (7 dimensions), cliché detection, reader questions, improvement suggestions, strengths, summary.

### 3.4 AuditResult

Contains: verdict (5-level scale), confidence score (0-1), disagreements, missed issues, hallucinations, weak critiques, summary.

## 4. Prompts

### 4.1 Strategy

Prompts are generated dynamically based on:
- Detected language (RU/EN)
- User-provided requirements
- Deterministic pre-analysis results

This ensures the LLM receives relevant context and produces critique in the appropriate language.

### 4.2 Primary Analyzer Prompt

The system prompt establishes the role (expert literary critic) and 10 critical rules:
1. Never rewrite — only analyze
2. Back claims with short quotes
3. Be specific and concrete
4. Score honestly
5. Look for "reader questions"
6. Check for clichés
7. Assess logic, pacing, voice, POV, consistency
8. Identify contradictions and unclear references
9. Provide bullet-point suggestions
10. Output valid JSON only

The user prompt includes the text, requirements, deterministic pre-analysis, and the exact JSON output schema.

### 4.3 Auditor Prompt

The system prompt establishes an adversarial meta-reviewer role with 8 missions:
1. Verify every factual claim
2. Detect hallucinations
3. Identify missed issues
4. Flag weak/vague points
5. Check quoted evidence exists
6. Assess score fairness
7. Provide confidence score
8. Output valid JSON only

## 5. LLM Client

### 5.1 Provider Modes

- **OpenAI mode** (default): Direct OpenAI API via `openai` Python package
- **LiteLLM mode**: Any OpenAI-compatible endpoint (LiteLLM proxy) supporting Claude, Gemini, local models

Both use the same `AsyncOpenAI` client; LiteLLM mode simply changes `base_url` and `api_key`.

### 5.2 Reliability

- Configurable retries with exponential backoff
- Per-model timeout settings
- JSON mode enforcement (`response_format: json_object`)
- Graceful error handling with fallback

### 5.3 Caching

Optional file-based cache keyed on (model, messages, temperature). Useful for development and repeated analysis of the same text.

## 6. Web UI

### 6.1 Stack

- Flask 3.x with Blueprint
- Vanilla JavaScript (no framework)
- ProxyFix for reverse proxy (nginx) deployment

### 6.2 Features

- Text input with live character counter (8192 limit)
- Requirements input
- Collapsible configuration editor
- Background analysis with progress polling
- Tab-based results view:
  - **Report**: Rendered Markdown
  - **JSON**: Interactive collapsible tree viewer
  - **Logs**: Raw log output
  - **History**: Previous runs with click-to-load

### 6.3 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/config` | GET | Current config (redacted) |
| `/api/analyze` | POST | Start analysis (returns run_id) |
| `/api/status/<id>` | GET | Poll run status/progress |
| `/api/result/<id>` | GET | Fetch completed result |
| `/api/cancel/<id>` | POST | Cancel running analysis |
| `/api/runs` | GET | List all runs |
| `/api/logs` | GET | List all log files |
| `/api/logs/<id>` | GET | Read specific log |

## 7. Configuration

JSON-based with environment variable overrides. Key config fields:

- `max_input_chars` (8192) — hard cap
- `max_report_chars` (65536) — soft cap for report length
- `models.primary.*` — primary model settings
- `models.audit.*` — audit model settings
- `provider` — "openai" or "litellm"
- `litellm.base_url`, `litellm.api_key` — LiteLLM proxy settings
- `enable_audit` — toggle audit step
- `enable_cache` — toggle response caching
- `verbosity` — 0/1/2
- `redact_secrets` — mask API keys in logs and config output

## 8. Deployment

### 8.1 Container

- Python 3.11-slim base
- Non-root user
- Volume mount for workspace (logs/runs/cache)
- Exposed port 8020

### 8.2 Targets

The Makefile mirrors lyrics-enhancer deployment pattern:
- `make deploy-setup` — one-time remote setup
- `make deploy` — build amd64 image, transfer, restart systemd service
- `make deploy-status/logs/stop/restart` — remote management

### 8.3 systemd

User-level systemd service (`prose-critique.service`) for persistent deployment.

## 9. Security

- API keys never logged (RedactingFormatter pattern-matches sk-* tokens)
- Config output always redacted unless explicitly unsafe
- Web UI does not accept API keys — they come from .env only
- File path traversal checks on run/log access
- Input size hard-capped at 8192 chars

## 10. Testing

- **Unit tests**: Deterministic analyzers (segmentation, language detection, repetition, readability, coreference)
- **Contract tests**: Pydantic model validation, config loading
- **Integration tests**: Full pipeline with real LLM (skipped without OPENAI_API_KEY)
