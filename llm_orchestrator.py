import sqlite3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import logging
from datetime import datetime
from pathlib import Path

import scrapetube
from youtube_transcript_api import YouTubeTranscriptApi

from config import (
    CHANNELS, DB_NAME, VIDEOS_PER_CHANNEL, RATE_LIMIT_SECONDS,
    SKIP_VIDEO_IDS, SKIP_TITLE_KEYWORDS, OUTPUT_JSONL, LOG_FILE,
    PREFILTER_ENABLED, LLM_BACKEND, CLI_COMMAND, CLI_FLAGS,
    EXTRACTION_INSTRUCTIONS_FILE, PREFILTER_INSTRUCTIONS_FILE,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project root — used to locate instruction files
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent


def setup_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,
            title TEXT,
            url TEXT,
            channel TEXT,
            status TEXT DEFAULT 'PENDING',
            published_date TEXT,
            extracted_data TEXT,
            error_msg TEXT
        )
    ''')
    conn.commit()
    try:
        c.execute("ALTER TABLE videos ADD COLUMN description_snippet TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    return conn


def fetch_transcript(video_id):
    """Fetch the transcript for a YouTube video using youtube-transcript-api."""
    api = YouTubeTranscriptApi()
    transcript = api.fetch(video_id)
    text = ' '.join(snippet.text for snippet in transcript)
    return text


# ---------------------------------------------------------------------------
# CLI workspace management
# ---------------------------------------------------------------------------

def _setup_cli_workspace(instruction_file):
    """Create an isolated temp workspace for the CLI invocation.

    The workspace contains:
      - CLAUDE.md: minimal directive to follow the instruction file
      - The instruction file (copied from project root)

    Returns the workspace directory path (caller should clean up).
    """
    workspace = tempfile.mkdtemp(prefix='cli_workspace_')

    # Minimal CLAUDE.md so the CLI doesn't load project context
    claude_md = Path(workspace) / 'CLAUDE.md'
    claude_md.write_text(
        "Follow the instruction file exactly. Return only JSON. "
        "Do not add commentary, markdown fences, or extra text.\n"
    )

    # Copy the instruction file into the workspace
    src = PROJECT_ROOT / instruction_file
    if not src.exists():
        raise FileNotFoundError(f"Instruction file not found: {src}")
    shutil.copy2(src, workspace)

    return workspace


def _run_cli(input_text, instruction_file):
    """Run the Claude CLI with the given input and instruction file.

    Sets up an isolated workspace, pipes input_text to the CLI, and
    returns the parsed JSON output.
    """
    workspace = _setup_cli_workspace(instruction_file)
    try:
        # Write the input text to a temp file in the workspace
        input_path = Path(workspace) / 'input.txt'
        input_path.write_text(input_text)

        # Build the CLI command
        cmd = [CLI_COMMAND, '-p']
        if CLI_FLAGS:
            cmd.extend(CLI_FLAGS.split())
        cmd.extend([
            '--append-system-prompt-file', instruction_file,
            '--output-format', 'json',
        ])

        log.debug("CLI command: %s", ' '.join(cmd))
        log.debug("CLI workspace: %s", workspace)

        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            cwd=workspace,
            timeout=300,  # 5-minute timeout per invocation
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(
                f"CLI exited with code {result.returncode}: {stderr}"
            )

        raw_output = result.stdout.strip()
        if not raw_output:
            raise RuntimeError("CLI returned empty output")

        # The CLI with --output-format json wraps the result in a JSON
        # envelope with a "result" field. Try to unwrap it.
        try:
            envelope = json.loads(raw_output)
            if isinstance(envelope, dict) and 'result' in envelope:
                inner = envelope['result']
                # The inner result might be a JSON string or already parsed
                if isinstance(inner, str):
                    # Strip markdown fences if present (safety net)
                    inner = inner.strip()
                    if inner.startswith("```"):
                        inner = inner.split("\n", 1)[1] if "\n" in inner else inner[3:]
                        if inner.endswith("```"):
                            inner = inner[:-3].strip()
                    return json.loads(inner)
                return inner
            # If no envelope, the output is the raw JSON
            return envelope
        except json.JSONDecodeError:
            # Try stripping markdown fences as a last resort
            cleaned = raw_output
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].strip()
            return json.loads(cleaned)

    finally:
        # Clean up the temp workspace
        shutil.rmtree(workspace, ignore_errors=True)


# ---------------------------------------------------------------------------
# Extraction and prefiltering
# ---------------------------------------------------------------------------

def extract_with_cli(title, transcript_text):
    """Send the transcript + title to Claude CLI for structured extraction."""
    input_text = f"Video title: {title}\n\nTranscript:\n{transcript_text}"
    return _run_cli(input_text, EXTRACTION_INSTRUCTIONS_FILE)


def prefilter_with_cli(title, description):
    """Use the CLI to decide if a video is worth extracting."""
    input_text = f"Title: {title}\nDescription: {description or '(no description available)'}"
    result = _run_cli(input_text, PREFILTER_INSTRUCTIONS_FILE)

    # The result should be a dict with a "result" text or just a string
    if isinstance(result, dict):
        answer = result.get('result', str(result))
    else:
        answer = str(result)

    return answer.strip()


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def fetch_candidates(conn, limit=None):
    log.info("Fetching video candidates from channels...")
    c = conn.cursor()
    max_videos = limit if limit else VIDEOS_PER_CHANNEL
    for channel, url in CHANNELS.items():
        log.info("Scraping %s (max %d videos)...", channel, max_videos)
        try:
            videos = scrapetube.get_channel(channel_url=url, limit=max_videos)
            count = 0
            for video in videos:
                if count >= max_videos:
                    break

                vid_id = video.get('videoId')
                if not vid_id:
                    continue
                count += 1

                c.execute("SELECT video_id FROM videos WHERE video_id = ?", (vid_id,))
                if c.fetchone():
                    continue

                title = video.get('title', {}).get('runs', [{}])[0].get('text', 'Unknown Title')
                vid_url = f"https://www.youtube.com/watch?v={vid_id}"

                # Extract published date and description snippet from scrapetube metadata
                published_text = video.get('publishedTimeText', {}).get('simpleText', '')
                desc_runs = video.get('descriptionSnippet', {}).get('runs', [])
                description_snippet = ' '.join(r.get('text', '') for r in desc_runs).strip() or None

                # Skip known off-topic videos by ID or generic title keywords
                status = 'PENDING'
                if vid_id in SKIP_VIDEO_IDS:
                    status = 'SKIPPED_BY_FILTER'
                elif any(kw in title.lower() for kw in SKIP_TITLE_KEYWORDS):
                    status = 'SKIPPED_BY_FILTER'

                c.execute('''
                    INSERT INTO videos (video_id, title, url, channel, status, published_date, description_snippet)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (vid_id, title, vid_url, channel, status, published_text, description_snippet))
            conn.commit()
        except KeyboardInterrupt:
            raise
        except Exception:
            log.exception("Error fetching %s", channel)


def prefilter_pending(conn, limit=None):
    """Use the CLI to reject non-candidate videos."""
    if not PREFILTER_ENABLED:
        log.info("Pre-filter disabled, skipping.")
        return

    c = conn.cursor()

    query = "SELECT video_id, title, description_snippet FROM videos WHERE status = 'PENDING'"
    if limit:
        query += f" LIMIT {int(limit)}"
    c.execute(query)
    rows = c.fetchall()

    if not rows:
        log.info("No PENDING videos to pre-filter.")
        return

    log.info("Pre-filtering %d PENDING videos via CLI...", len(rows))
    for idx, (vid_id, title, desc) in enumerate(rows):
        try:
            answer = prefilter_with_cli(title, desc)
            if answer.upper().startswith('NO'):
                log.info("[%d/%d] REJECTED: %s — %s", idx + 1, len(rows), title, answer)
                c.execute(
                    "UPDATE videos SET status = 'PREFILTER_REJECTED', error_msg = ? WHERE video_id = ?",
                    (answer, vid_id),
                )
            else:
                log.info("[%d/%d] PASSED: %s — %s", idx + 1, len(rows), title, answer)
            conn.commit()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            log.warning("Pre-filter failed for %s, leaving as PENDING: %s", title, e)

        time.sleep(RATE_LIMIT_SECONDS)


def process_pending(conn, retry_failed=False, limit=None):
    c = conn.cursor()

    statuses = ['PENDING']
    if retry_failed:
        statuses.extend(['FAILED_TRANSCRIPT', 'FAILED_LLM'])
        log.info("Retrying previously failed videos as well.")

    placeholders = ','.join('?' for _ in statuses)
    query = f"SELECT video_id, title, url, channel, published_date FROM videos WHERE status IN ({placeholders})"
    if limit:
        query += f" LIMIT {int(limit)}"
    c.execute(query, statuses)
    rows = c.fetchall()

    log.info("Found %d videos to process.", len(rows))
    for idx, (vid_id, title, url, channel, published_date) in enumerate(rows):
        log.info("[%d/%d] Processing: %s", idx + 1, len(rows), title)

        # Step 1: Fetch transcript
        try:
            transcript_text = fetch_transcript(vid_id)
        except Exception as e:
            log.warning(" -> Transcript fetch failed for %s: %s", title, e)
            c.execute(
                "UPDATE videos SET status = 'FAILED_TRANSCRIPT', error_msg = ? WHERE video_id = ?",
                (str(e), vid_id),
            )
            conn.commit()
            continue

        # Step 2: Send transcript to CLI for extraction
        try:
            llm_data = extract_with_cli(title, transcript_text)

            # Inject our known metadata
            llm_data['video_link'] = url
            llm_data['channel'] = channel
            llm_data['published_date'] = published_date or None

            c.execute(
                "UPDATE videos SET status = 'COMPLETED', extracted_data = ?, error_msg = NULL WHERE video_id = ?",
                (json.dumps(llm_data), vid_id),
            )
            conn.commit()
            log.info(" -> Extraction successful!")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            log.exception(" -> Extraction failed for %s", title)
            c.execute(
                "UPDATE videos SET status = 'FAILED_LLM', error_msg = ? WHERE video_id = ?",
                (str(e), vid_id),
            )
            conn.commit()

        time.sleep(RATE_LIMIT_SECONDS)


def export_to_jsonl(conn):
    c = conn.cursor()
    c.execute("SELECT title, url, channel, extracted_data FROM videos WHERE status = 'COMPLETED'")
    rows = c.fetchall()

    if not rows:
        log.info("No completed records to export.")
        return

    log.info("Exporting %d records to %s", len(rows), OUTPUT_JSONL)
    with open(OUTPUT_JSONL, "w") as f:
        for title, url, channel, data in rows:
            entry = json.loads(data)
            entry['_vid_title'] = title
            f.write(json.dumps(entry) + '\n')


def print_status(conn):
    c = conn.cursor()
    c.execute("SELECT status, COUNT(*) FROM videos GROUP BY status")
    rows = c.fetchall()
    log.info("--- Database Status ---")
    for status, count in rows:
        log.info("  %s: %d", status, count)


def main():
    retry_failed = '--retry' in sys.argv

    limit = None
    for arg in sys.argv[1:]:
        if arg.startswith('--limit='):
            limit = int(arg.split('=', 1)[1])
        elif arg.isdigit():
            limit = int(arg)

    log.info("LLM backend: %s (command: %s)", LLM_BACKEND, CLI_COMMAND)
    conn = setup_db()
    fetch_candidates(conn, limit=limit)
    prefilter_pending(conn, limit=limit)
    process_pending(conn, retry_failed=retry_failed, limit=limit)
    export_to_jsonl(conn)
    print_status(conn)


if __name__ == "__main__":
    main()
