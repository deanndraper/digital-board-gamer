#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "[$(date)] Starting publish pipeline..."

# Pull latest changes
git pull --ff-only origin main 2>/dev/null || true

# Load environment
set -a
source .env
set +a

# Activate venv
source .venv/bin/activate

# Step 1: Run orchestrators for all channels
echo "[$(date)] Running multi-channel orchestrator..."
python llm_orchestrator.py
python llm_orchestrator.py --retry

echo "[$(date)] Running BoardGameCo orchestrator..."
SCANNER_CONFIG=boardgameco_config.yaml python llm_orchestrator.py
SCANNER_CONFIG=boardgameco_config.yaml python llm_orchestrator.py --retry

# Step 2: Generate the static site (reads all channel_insights_*.jsonl)
echo "[$(date)] Generating site..."
python generate_site.py

# Step 3: Commit and push if there are changes
if git diff --quiet docs/ channel_insights_*.jsonl 2>/dev/null; then
    echo "[$(date)] No changes to publish."
else
    echo "[$(date)] Changes detected, committing..."
    git add docs/ channel_insights_*.jsonl
    git commit -m "chore: update game data and regenerate site ($(date +%Y-%m-%d))"
    git push origin main
    echo "[$(date)] Published successfully."
fi

echo "[$(date)] Done."
