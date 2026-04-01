# CLI-Based LLM Processing — Design Spec

## Status: Discovery / Proof of Concept

## Problem
The current pipeline uses the Anthropic API directly for LLM calls (prefilter + extraction). This requires API key management, token-level retry logic, chunking code, prompt template management in YAML, and JSON parsing/fence-stripping. Long transcripts (50+ game lists) lose data due to trimming.

## Proposed Solution
Replace API calls with Claude Code CLI (`claude -p`) invocations. The CLI handles context management, chunking, retries, and structured output natively. Extraction instructions move from YAML prompt blocks to readable .md instruction files.

## Why This Makes Sense
- Pro plan tokens are underutilized (~5% usage) — redirect capacity from interactive use to batch processing
- CLI is model-agnostic at the config level — switching providers means changing the CLI command, not rewriting code
- Long transcripts are handled by the CLI's own context management — no Python chunking logic needed
- Instruction files (.md) are easier to read, edit, and version than YAML prompt blocks
- 5-hour token window can be managed by queuing — batch pipelines tolerate delays naturally

## Architecture Change

### Current (API-based)
```
Python fetches transcript
  → Python trims/chunks transcript
  → Python formats prompt from YAML template
  → Python calls Anthropic API
  → Python strips markdown fences
  → Python parses JSON
  → Python handles retries/backoff
  → Python stores result
```

### Proposed (CLI-based)
```
Python fetches transcript
  → Python saves transcript to temp file
  → Python calls: claude --bare -p < transcript.txt
      with --append-system-prompt-file extraction_instructions.md
      with --output-format json
      with --json-schema '{...}'
  → CLI handles context, chunking, retries internally
  → Python captures structured JSON output
  → Python stores result
```

## What Stays in Python
- State management (SQLite — video status tracking)
- YouTube scraping (scrapetube — channel video enumeration)
- Transcript fetching (youtube-transcript-api)
- Site generation (generate_site.py — JSONL → HTML)
- Publish automation (publish.sh)
- BGA/BGG scraping (bga_scraper.py — no LLM involved)

## What Moves to CLI + Instruction Files
- Prefiltering (is this video a review? YES/NO)
- Game data extraction (transcript → structured JSON)
- Long transcript handling (chunking, merging — handled by CLI context)
- Prompt engineering (YAML blocks → .md instruction files)

## New Files

### .claude/skills/prefilter/SKILL.md
Prefilter instruction — given a title and description, respond YES or NO with reason.

### .claude/skills/extract-games/SKILL.md
Extraction instruction — given a transcript, extract games with scores, rankings, opinions. Includes the full JSON schema and extraction rules currently in the YAML configs.

### extraction_instructions.md (alternative to skills)
Standalone instruction file loadable via `--append-system-prompt-file`. May be simpler than skills for batch processing with `--bare` mode.

## CLI Invocation Patterns

### Prefilter
```bash
echo "Title: ${title}\nDescription: ${description}" | \
  claude --bare -p \
    --append-system-prompt-file prefilter_instructions.md \
    --output-format json \
    --json-schema '{"type":"object","properties":{"answer":{"type":"string","enum":["YES","NO"]},"reason":{"type":"string"}},"required":["answer","reason"]}'
```

### Extraction
```bash
cat transcript.txt | \
  claude --bare -p \
    --append-system-prompt-file extraction_instructions.md \
    --output-format json \
    --json-schema '{"type":"object","properties":{"games":{"type":"array"},"summary":{"type":"string"},"classification":{"type":"string"}},"required":["games","summary","classification"]}'
```

## Config Changes
New YAML fields per config:
```yaml
llm:
  backend: 'cli'              # 'api' or 'cli'
  cli_command: 'claude'        # which CLI to invoke
  cli_flags: '--bare'          # additional flags
  prefilter_instructions: 'prefilter_instructions.md'
  extraction_instructions: 'extraction_instructions.md'
```

Existing API fields (`model`, `rate_limit_seconds`, etc.) remain for backward compatibility. When `backend: api`, current behavior is unchanged.

## Token Window Management
- If CLI returns a capacity/rate error, log it and mark remaining videos as PENDING
- publish.sh can be scheduled to retry (cron runs daily, picks up where it left off)
- Optional: track estimated token usage per run and pause before hitting limits

## What We Lose
- Fine-grained control over which model handles each call (CLI uses whatever model is configured in the user's Claude settings)
- Precise token counting and cost tracking per API call
- Concurrent API calls (CLI is sequential by nature — but we were already sequential due to rate limiting)

## What We Gain
- No API key management for LLM calls
- No chunking/merge code in Python
- No retry/backoff code in Python
- No JSON fence-stripping code
- Structured output validation via --json-schema
- Instruction files are readable markdown, not embedded YAML strings
- Model-agnostic — swap CLI tools without code changes
- Leverages unused Pro plan capacity

## Proof of Concept Plan
1. Pick one video (the "Hottest and Not-So-Hot" 92-game video)
2. Write extraction_instructions.md
3. Fetch its transcript, save to file
4. Call claude --bare -p with the instruction file and schema
5. Compare output to current API-based result
6. Measure: token usage, time taken, number of games captured
7. If successful, implement the backend switch in llm_orchestrator.py

## Migration Path
- Phase 1: POC with one video (validate approach)
- Phase 2: Add `backend: cli` option to config, implement CLI wrapper function
- Phase 3: Run both backends side-by-side on same videos, compare results
- Phase 4: Switch default to CLI, keep API as fallback
- Phase 5: Remove API-specific code (chunking, retry, fence-stripping) once CLI is proven stable

## Open Questions
- Does `--json-schema` work reliably with large outputs (90+ game objects)?
- What happens when the 5-hour token window is exhausted mid-batch?
- Should we use skills or standalone instruction files for batch mode?
- What's the per-invocation overhead of CLI vs API (startup time)?
