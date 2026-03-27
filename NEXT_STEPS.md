# Digital Board Gamer — Project Overview

## What This Project Does

Scrapes YouTube board game channels, extracts structured game data using Claude, and publishes results to a static website. Also scrapes Board Game Arena and BoardGameGeek for game metadata.

**Live site:** https://games.transformativehelp.com/

## Pipelines

### 1. YouTube Channel Scanner
Extracts game reviews, rankings, and opinions from video transcripts using Claude (Sonnet for extraction, Haiku for prefiltering).

**Channels (default config):** Digital Board Gamer, Game-Night with Saisha, Peaky Boardgamer
**Alternate config:** BoardGameCo (@boardgameco)

```bash
# Run default 3-channel pipeline
source .venv/bin/activate
export ANTHROPIC_API_KEY="your-key-here"
python llm_orchestrator.py

# Run BoardGameCo pipeline
SCANNER_CONFIG=boardgameco_config.yaml python llm_orchestrator.py

# Retry failed videos
python llm_orchestrator.py --retry

# Limit processing
python llm_orchestrator.py --limit=10
```

### 2. BGA Game Scraper
Scrapes the top 200 most-played games on Board Game Arena with full metadata (designer, publisher, complexity, strategy, luck, interaction, player count, duration, tags, box art).

```bash
python bga_scraper.py              # scrape top 200
python bga_scraper.py --limit=50   # scrape top 50
python bga_scraper.py --retry      # retry failed
python bga_scraper.py --export-only
```

### 3. Static Site Generator
Reads all `channel_insights_*.jsonl` files and generates `docs/index.html` with a sortable, filterable Tabulator table.

```bash
python generate_site.py
```

### 4. Full Publish Pipeline
Runs all orchestrators, regenerates the site, and pushes to GitHub Pages.

```bash
./publish.sh
```

## Key Files

| File | Purpose |
|------|---------|
| `llm_orchestrator.py` | YouTube channel scanner — scrape, extract, export |
| `bga_scraper.py` | BGA game metadata scraper + BGG enrichment |
| `generate_site.py` | Static site generator (reads all channel_insights_*.jsonl) |
| `publish.sh` | End-to-end automation: scrape → extract → generate → push |
| `config.py` | YAML config loader for channel scanner |
| `scanner_config.yaml` | Config for 3 default channels |
| `boardgameco_config.yaml` | Config for BoardGameCo channel |
| `bga_config.yaml` | Config for BGA scraper |

## Data Files

| File | Contents |
|------|----------|
| `channel_insights_multi.jsonl` | Extracted data from 3 default channels |
| `channel_insights_boardgameco.jsonl` | Extracted data from BoardGameCo |
| `bga_games.jsonl` | BGA top 200 game metadata + BGG ratings |
| `BGA_Top_200_Games.xlsx` | Excel export of BGA/BGG data (44 columns) |
| `BGA_Popular_100_Games.csv` | BGA popular-now snapshot (2026-03-26) |

## Databases

| Database | Contents |
|----------|----------|
| `orchestrator_state.db` | State tracking for 3 default channels |
| `boardgameco_state.db` | State tracking for BoardGameCo |
| `bga_games.db` | BGA game metadata, BGG ratings, popular-now snapshots |

## Environment

- Python >=3.11
- `ANTHROPIC_API_KEY` required for YouTube pipeline
- Virtual environment in `.venv/`
- Site published via GitHub Pages at https://games.transformativehelp.com/
