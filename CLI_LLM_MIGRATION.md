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

## CLI Workspace

The CLI runs in an isolated directory so it doesn't load the project's CLAUDE.md, code, git history, or skills — avoiding wasted tokens and confused context.

**Location:** `/tmp/cli_workspace/`

**Contents:**
```
/tmp/cli_workspace/
├── CLAUDE.md                     # Minimal: "Follow the instruction file exactly. Return only JSON."
├── extraction_instructions.md    # Game extraction rules + JSON schema
├── prefilter_instructions.md     # YES/NO prefilter rules
└── transcript.txt                # Temp — written per video, overwritten each time
```

**Setup:** Python creates this directory and copies instruction files at pipeline startup. The transcript file is overwritten for each video. The directory is outside the project tree entirely — explicit, visible, no gitignore needed.

## New Files (in project root, copied to workspace at runtime)

### extraction_instructions.md
Full extraction rules, JSON schema, field definitions. Already created during POC.

### prefilter_instructions.md
Given a title and description, respond YES or NO with reason.

## CLI Invocation Patterns

All invocations use `cwd=/tmp/cli_workspace/` so the CLI only sees the workspace files.

### Prefilter
```bash
cd /tmp/cli_workspace && \
echo "Title: ${title}\nDescription: ${description}" | \
  claude -p \
    --append-system-prompt-file prefilter_instructions.md \
    --output-format json
```

### Extraction
```bash
cd /tmp/cli_workspace && \
cat transcript.txt | \
  claude -p \
    --append-system-prompt-file extraction_instructions.md \
    --output-format json
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

## POC Results (2026-04-01)

Tested with "The Hottest and Not-So-Hot Games of 2025 on BGA" video (92 games shown, 1,732 word transcript).

| Metric | API (Sonnet) | CLI (Opus via Pro) |
|--------|-------------|-------------------|
| Games extracted | 31 | 31 |
| Time | ~38s | ~38s |
| Cost | ~$0.02 | $0.155 (Opus pricing) / $0 against Pro plan |
| Chunking needed | No | No |

**Findings:**
- CLI extracted same data as API — functionally equivalent
- CLI used Opus (project default) — higher quality model at no API cost via Pro plan
- 92 vs 31 gap is a transcript limitation (games shown on screen, not spoken) — neither API nor CLI can fix this
- `--bare` flag fails auth — must run without it, hence the isolated workspace is important
- Output is JSON envelope with `result` field containing the extraction (sometimes with markdown fences)
- Need to test `--json-schema` flag to eliminate fences

## Open Questions
- Does `--json-schema` work reliably with large outputs (90+ game objects)?
- What happens when the 5-hour token window is exhausted mid-batch?
- What's the per-invocation overhead of CLI vs API (startup time)?
- Can we specify model via CLI flag to control cost/quality tradeoff?
- The workspace CLAUDE.md — how minimal can it be while still directing the CLI correctly?
