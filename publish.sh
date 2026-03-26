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

# Step 1: Run the orchestrator (scrape + extract + export JSONL)
echo "[$(date)] Running orchestrator..."
python llm_orchestrator.py

# Step 2: Retry any previously failed videos
echo "[$(date)] Retrying failed videos..."
python llm_orchestrator.py --retry

# Step 3: Generate the static site
echo "[$(date)] Generating site..."
python generate_site.py

# Step 4: Commit and push if there are changes
if git diff --quiet docs/ Complete_Insights.jsonl 2>/dev/null; then
    echo "[$(date)] No changes to publish."
else
    echo "[$(date)] Changes detected, committing..."
    git add docs/ Complete_Insights.jsonl
    git commit -m "chore: update game data and regenerate site ($(date +%Y-%m-%d))"
    git push origin main
    echo "[$(date)] Published successfully."
fi

echo "[$(date)] Done."
