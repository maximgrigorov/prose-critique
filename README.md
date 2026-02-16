# Prose Critique

**Local-first, LLM-powered prose analysis and critique tool.**

Produces extremely detailed critique reports for prose text (up to 8192 characters) with automatic language detection (English/Russian), deterministic pre-analysis, LLM-based deep critique, and optional cross-model audit.

## Features

- **One-pass analysis** — no rewriting or "polishing", only analysis and critique
- **Two-model cross-check** — optional auditor model verifies the primary critique, flags hallucinations
- **Deterministic pre-analysis** — language detection, readability metrics, repetition detection, coreference flags, dangling modifier heuristics (all local, no LLM)
- **Auto-requirements** — when no requirements are provided, the system automatically generates 15–20+ context-aware analysis criteria based on text type, detected issues, and baseline prose quality standards
- **Dual output** — human-readable Markdown report + structured JSON with per-paragraph analysis
- **Bilingual** — auto-detects Russian/English, produces critique in the same language
- **Web UI** — text input with char counter, config editor, results viewer, logs, run history
- **CLI** — scriptable command-line interface
- **Container** — Podman-compatible image for deployment
- **Flexible LLM backend** — OpenAI direct or any model via LiteLLM proxy

## Quick Start

### 1. Install

```bash
# Clone
git clone https://github.com/maximgrigorov/prose-critique.git
cd prose-critique

# Install dependencies
make install        # CLI only
make install-web    # CLI + Web UI
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 3. Run (CLI)

```bash
# Analyze the sample text
make run

# Custom files
python main.py -s mytext.txt -r requirements.txt -o report.md -j report.json

# Disable audit for faster/cheaper runs
python main.py -s mytext.txt --no-audit
```

### 4. Run (Web UI)

```bash
make web           # Dev mode at http://127.0.0.1:8020
make web-prod      # Production mode at 0.0.0.0:8020
```

### 5. Run (Container)

```bash
make build-container
make run-container
# Open http://localhost:8020
```

## Requirements (Analysis Criteria)

### What Are Requirements?

**Requirements** are instructions that tell the LLM analyzer **what to look for** in the text. They are the most important input for getting a useful critique. Think of them as a "rubric" or "checklist" that the critic follows.

Without requirements, the tool generates a comprehensive baseline set automatically (see [Auto-Generated Requirements](#auto-generated-requirements)). With custom requirements, you get a targeted critique focused on exactly what matters to you.

### When to Use Custom Requirements

| Scenario | Use Requirements? | Why |
|----------|-------------------|-----|
| Quick general check | No (auto-generated is fine) | Baseline covers all common issues |
| Preparing for publication | **Yes** | Focus on publisher/editor concerns |
| Self-editing a specific aspect | **Yes** | Zero in on style, pacing, dialogue, etc. |
| Writing workshop feedback | **Yes** | Match the workshop's evaluation criteria |
| Checking translation quality | **Yes** | Add translation-specific criteria |
| Genre-specific review | **Yes** | Add genre conventions as requirements |

### How to Write Requirements

Requirements are plain text — one criterion per line, each describing **what to analyze** and optionally **how to evaluate** it. The format is flexible, but here are best practices:

#### Structure

```
<ASPECT>: <WHAT TO CHECK>. <OPTIONAL: HOW TO EVALUATE OR WHAT IS ACCEPTABLE>.
```

#### Example Requirements (English)

```
Sentence complexity: Flag sentences longer than 20 words. Suggest how to split compound sentences without losing meaning.
Dialogue naturalness: Check that dialogue sounds like real speech, not written prose. Each character should have a distinct voice.
Pacing: Evaluate whether scenes have appropriate length relative to their importance. Flag rushed climactic moments or drawn-out descriptions.
Emotional authenticity: Assess whether character emotions are shown through actions and body language, not just stated.
Show vs Tell: Identify passages where the author tells the reader what to feel instead of showing it through scene construction.
Point of view consistency: The text should maintain third-person limited POV throughout. Flag any head-hopping or POV breaks.
Historical accuracy: The story is set in 1920s Paris. Flag any anachronistic language, objects, or social norms.
Metaphor quality: Evaluate metaphors and similes for freshness and precision. Flag mixed metaphors and dead metaphors.
Target audience: The text is aimed at young adults (16-20). Flag language or concepts that may be too complex or too simplistic.
Foreshadowing: Check whether plot hints are too obvious (spoiling) or too subtle (unnoticeable on first read).
```

#### Example Requirements (Russian)

```
Сложность предложений: Отмечайте предложения длиннее 20 слов. Предлагайте варианты разбивки сложных конструкций.
Естественность диалогов: Проверьте, звучат ли реплики как живая речь. У каждого персонажа должен быть свой голос.
Темп повествования: Оцените, соразмерны ли сцены их важности. Отметьте скомканные кульминации или затянутые описания.
Эмоциональная достоверность: Оцените, показаны ли эмоции через действия и поведение, а не просто названы.
Показ vs Рассказ: Определите места, где автор рассказывает читателю, что чувствовать, вместо того чтобы показывать через сцену.
Последовательность точки зрения: Текст должен сохранять единую точку зрения. Отметьте переключения между персонажами.
Историческая достоверность: Действие происходит в Москве 1920-х. Отметьте анахронизмы в языке, предметах, нормах поведения.
Качество метафор: Оцените метафоры и сравнения на свежесть и точность. Отметьте смешанные и мёртвые метафоры.
Целевая аудитория: Текст рассчитан на подростков (14-18 лет). Отметьте слишком сложные или слишком примитивные формулировки.
Предзнаменования: Проверьте, не слишком ли очевидны подсказки сюжета (спойлеры) или слишком незаметны.
```

### Preparing Requirements with AI

You can ask any LLM (e.g., GPT, Claude) to generate requirements for your text. Here is a prompt template:

```
I have a prose text excerpt (in Russian/English) that I want to analyze for quality.
The text is [DESCRIBE: genre, context, target audience, what you're worried about].

Generate a set of 10-20 analysis requirements for a literary critique tool.
Each requirement should:
1. Name a specific aspect of prose quality (one aspect per line)
2. Explain what to check
3. Optionally specify what is acceptable vs problematic
4. Be in the same language as the text

Format: one requirement per line, like:
<Aspect>: <What to check>. <Evaluation guidance>.

Focus on: [LIST YOUR CONCERNS, e.g., "sentence clarity, pacing, dialogue quality,
clichés, logical consistency, age-appropriate language"]
```

#### Example AI Conversation

**You:** I have a Russian fairy-tale style text about a fairy and magical creatures. The text is for children aged 8-12. I'm worried about sentence complexity, archaisms being too hard, and pacing. Generate requirements.

**AI might produce:**

```
Понятность для детей 8-12 лет: Все ли слова и конструкции доступны целевой аудитории? Отметьте фразы, требующие словаря.
Архаизмы: Перечислите все устаревшие/стилизованные слова. Оцените, понятны ли они из контекста или нуждаются в пояснении.
Длина предложений: Для детского текста предложения не должны превышать 15-18 слов. Отметьте все более длинные.
Темп повествования: Оцените, не затянуто ли описание и не скомкано ли действие. Дети теряют интерес при затянутых описаниях.
Визуальность: Достаточно ли ярко описаны сцены? Может ли ребёнок представить картинку?
Мотивация персонажей: Понятно ли, почему персонажи поступают так, а не иначе?
Логика волшебного мира: Последовательны ли правила магии? Нет ли противоречий?
Диалоги: Различимы ли голоса персонажей? Не слишком ли взрослые реплики?
Страшные элементы: Есть ли фрагменты, которые могут напугать ребёнка? Уместны ли они?
Мораль/урок: Если подразумевается нравоучение, подано ли оно ненавязчиво?
```

### Auto-Generated Requirements

When no requirements are provided (the Requirements field is empty), the tool **automatically generates** a comprehensive set of analysis criteria. This is NOT a simple generic prompt — the system:

1. **Starts with 15 baseline criteria** covering universal prose quality aspects:
   - Comprehensibility, clarity, sentence complexity
   - Excessive pathos, stylistic affectation
   - Clichés, logical consistency, terminology burden
   - Realistic descriptions, pacing, pronoun clarity
   - Redundancy, voice consistency, dialogue, emotional impact

2. **Adds conditional criteria** based on what the deterministic pre-analysis found:
   - Long sentences detected → adds sentence complexity focus
   - Low vocabulary richness → adds repetition analysis focus
   - Coreference issues → adds pronoun clarity focus
   - Dangling modifiers → adds modifier analysis focus
   - Short text → tells the LLM not to penalize for incompleteness

3. **Adds text-type specific criteria** by detecting content signals:
   - **Dialogue present** → adds dialogue naturalness and character voice criteria
   - **Fantasy/fairy-tale elements** → adds magical consistency, whimsy vs clarity balance
   - **Children's literature markers** → adds age-appropriate language criteria
   - **Archaic/stylized language** → adds archaism assessment, consistency of stylization

All auto-generated requirements are in the text's detected language (Russian or English).

### Requirements in the Web UI

In the Web UI, paste your requirements into the "Requirements" text area. If left empty, auto-generated requirements are used. You can see the full auto-generated requirements in the run logs.

### Requirements in CLI

```bash
# From a file
python main.py -s text.txt -r requirements.txt

# Without requirements (auto-generated)
python main.py -s text.txt
```

### Tips for Better Requirements

1. **Be specific, not generic.** "Check grammar" is too vague. "Flag subject-verb agreement errors and comma splices" is actionable.
2. **Include context.** Tell the analyzer what the text is: genre, audience, setting period, author intent.
3. **Prioritize.** Put your most important concerns first. The LLM pays more attention to earlier items.
4. **Set thresholds.** "Sentences over 20 words" is better than "long sentences."
5. **Mention what's OK.** "Archaic language is intentional and acceptable, but flag inconsistent use" prevents false positives.
6. **Use the text's language.** Write Russian requirements for Russian text. The entire pipeline is bilingual.
7. **10-20 requirements is ideal.** Fewer than 5 gives shallow analysis; more than 25 dilutes focus.

## Architecture

```
main.py                          # CLI entry point
modules/
  config.py                      # Config loading (.json + .env)
  models.py                      # Pydantic data models
  logger.py                      # Logging with per-run files
  llm_client.py                  # Async OpenAI/LiteLLM client
  orchestrator.py                # Pipeline coordinator
  agents/
    deterministic_analyzers.py   # Local text analysis (no LLM)
    primary_analyzer.py          # Primary LLM critique agent
    auditor.py                   # Auditor/cross-check agent
    report_builder.py            # Markdown + JSON report generation
  utils/
    language.py                  # Language detection
    segmentation.py              # Paragraph/sentence splitting (razdel)
    heuristics.py                # Repetition, readability, coreference
    prompts.py                   # Dynamic prompt templates (EN/RU)
    auto_requirements.py         # Auto-generated requirements system
web/
  app.py                         # Flask web application
  templates/                     # HTML templates
  static/                        # CSS + JavaScript
tests/                           # Unit and contract tests
workspace/                       # Logs, runs, cache (gitignored)
```

## Pipeline Flow

```
Input Text + Requirements (or auto-generated)
        │
        ▼
┌─────────────────────┐
│ Deterministic        │  Language detection, sentence splitting (razdel),
│ Pre-Analysis         │  readability, repetitions, coreference
└─────────┬───────────┘
          │
          ▼ (if no requirements)
┌─────────────────────┐
│ Auto-Requirements    │  Baseline criteria + conditional findings +
│ Generator            │  text-type detection (fairy-tale, dialogue, etc.)
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Primary LLM         │  Structural outline, local issues,
│ Analyzer             │  global issues, scores, clichés,
│                      │  reader questions, suggestions
└─────────┬───────────┘
          │
          ▼ (optional)
┌─────────────────────┐
│ Auditor LLM         │  Verifies claims, flags hallucinations,
│ (Cross-Check)        │  finds missed issues, rates confidence
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Report Builder       │  Markdown report + JSON report
└─────────────────────┘
```

## Configuration

See `example_config.json` for all options:

| Key | Default | Description |
|-----|---------|-------------|
| `max_input_chars` | 8192 | Hard cap on input text length |
| `max_report_chars` | 65536 | Soft cap on report length |
| `models.primary.model` | gpt-4o | Primary analyzer model |
| `models.audit.model` | gpt-4o-mini | Auditor model |
| `provider` | openai | `"openai"` or `"litellm"` |
| `enable_audit` | true | Enable the audit cross-check step |
| `enable_cache` | false | Cache LLM responses (see [Caching](#caching)) |
| `verbosity` | 1 | 0=warn, 1=info, 2=debug |
| `redact_secrets` | true | Mask API keys in logs |

### LiteLLM Mode

To use Claude, Gemini, or local models via LiteLLM proxy:

```json
{
  "provider": "litellm",
  "litellm": {
    "base_url": "http://alma:4000",
    "api_key": "your-litellm-key"
  },
  "models": {
    "primary": { "model": "claude-sonnet-4.5", "temperature": 0.3, "max_tokens": 16384, "timeout": 420 },
    "audit": { "model": "gpt-4o-mini", "temperature": 0.2, "max_tokens": 8192, "timeout": 180 }
  }
}
```

**Note on Anthropic models:** Claude does not support `response_format: json_object`. The tool automatically detects Claude models and uses explicit prompting + robust JSON extraction instead. You do not need to configure anything special.

### Caching

Enable caching (`"enable_cache": true`) to save LLM responses to disk. This is useful when:
- **Developing/debugging** — re-run the same text without paying for LLM calls
- **Testing prompt changes** — compare outputs without re-querying the model
- **Demonstrating** — reproduce results without API access

Cache is stored in `workspace/cache/` as text files keyed by model + messages + temperature hash.

**Do NOT enable caching** in production when analyzing different texts — it only returns cached results for the exact same input.

## Model Compatibility

| Model | Provider | JSON Parsing | Notes |
|-------|----------|-------------|-------|
| gpt-4o | OpenAI | Native JSON mode | Best balance of quality and speed |
| gpt-4o-mini | OpenAI | Native JSON mode | Good for auditor role |
| claude-sonnet-4.5 | Anthropic/LiteLLM | Extraction from text | Slow (2-5 min), expensive, high quality |
| gemini-2.5-flash | Google/LiteLLM | Extraction from text | Fast, good quality |

## Testing

```bash
make test
```

Tests include:
- **Unit tests** for deterministic analyzers (segmentation, language detection, repetition)
- **Contract tests** that validate data model schemas (no API keys needed)
- **Integration tests** (optional, requires `OPENAI_API_KEY` or LiteLLM proxy)

## Deployment

```bash
# First-time setup on alma
make deploy-setup

# Build and deploy
make deploy

# Monitor
make deploy-status
make deploy-logs
```

## License

MIT
