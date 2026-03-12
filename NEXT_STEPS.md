# Digital Board Gamer — Next Steps

## Project Overview

Scrapes YouTube channels for board game content, sends each video URL to Gemini for structured data extraction, and exports results to `Complete_Insights.jsonl`.

**Channels:** Digital Board Gamer, Game-Night with Saisha, Peaky Boardgamer

## Current State

| Status            | Count |
|-------------------|-------|
| COMPLETED         | 9     |
| PENDING           | 139   |
| SKIPPED_BY_FILTER | 2     |

- 9 videos already processed with the current prompt schema
- 139 videos awaiting processing (includes 9 that were reset for schema consistency)
- 2 known off-topic videos explicitly skipped via `SKIP_VIDEO_IDS` in `config.py`
- Output file: `Complete_Insights.jsonl` (9 clean records)

## What To Do Next

### 1. Process the next batch of videos

```bash
# Activate the virtual environment
source .venv/bin/activate

# Set the API key
export GEMINI_API_KEY="AIzaSyBfOKddr2rjzenMHfnjOPNAdcQzZDIaGeU"

# Process 10 at a time (recommended to monitor quality)
python llm_orchestrator.py --limit=10

# Or process all 139 remaining at once
python llm_orchestrator.py
```

The script will automatically:
1. Scrape channels for any new videos (adds to DB if not already present)
2. Send each PENDING video to Gemini for extraction
3. Export all COMPLETED records to `Complete_Insights.jsonl`
4. Print a status summary

### 2. Retry any failed videos

```bash
python llm_orchestrator.py --retry --limit=10
```

This re-attempts videos with status `FAILED_TRANSCRIPT` or `FAILED_LLM`.

### 3. Check status without processing

```bash
sqlite3 orchestrator_state.db "SELECT status, COUNT(*) FROM videos GROUP BY status"
```

### 4. Review output

```bash
# Count records
wc -l Complete_Insights.jsonl

# Pretty-print a single record
head -1 Complete_Insights.jsonl | python -m json.tool

# List all video titles in output
python -c "import json; [print(json.loads(l).get('_vid_title','')) for l in open('Complete_Insights.jsonl')]"
```

### 5. Skip a new off-topic video

If you spot an off-topic video in the output, add its video ID to `SKIP_VIDEO_IDS` in `config.py`, then update its status in the DB:

```bash
sqlite3 orchestrator_state.db "UPDATE videos SET status = 'SKIPPED_BY_FILTER' WHERE video_id = 'VIDEO_ID_HERE'"
```

Then re-export:
```bash
python llm_orchestrator.py --limit=0
```

## Key Files

| File | Purpose |
|------|---------|
| `llm_orchestrator.py` | Main pipeline — scrape, extract, export |
| `config.py` | Shared constants, skip lists, channel URLs |
| `orchestrator_state.db` | SQLite state tracking (video status) |
| `Complete_Insights.jsonl` | Extracted data output (one JSON per line) |
| `extract_all.py` | Fuzzy-match against existing spreadsheet |
| `validate_data.py` | Cross-reference spreadsheet vs channel videos |

## CLI Reference

```
python llm_orchestrator.py [OPTIONS]

Options:
  --limit=N    Process at most N pending videos (default: all)
  N            Same as --limit=N (positional shorthand)
  --retry      Also retry FAILED_TRANSCRIPT and FAILED_LLM videos
```
