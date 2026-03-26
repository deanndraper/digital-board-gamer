import sqlite3
import json
import os
import re
import sys
import time
import logging
from datetime import datetime

import anthropic
import scrapetube
from youtube_transcript_api import YouTubeTranscriptApi

from config import (
    CHANNELS, DB_NAME, LLM_MODEL, VIDEOS_PER_CHANNEL, RATE_LIMIT_SECONDS,
    SKIP_VIDEO_IDS, SKIP_TITLE_KEYWORDS, EXTRACTION_PROMPT, OUTPUT_JSONL, LOG_FILE,
    PREFILTER_ENABLED, PREFILTER_MODEL, PREFILTER_PROMPT, MAX_TRANSCRIPT_WORDS,
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


def trim_transcript(text, max_words):
    """Trim long transcripts, keeping the first 1000 and last (max-1000) words.

    Rationale: reviewers state game names at the start and scores/verdicts at
    the end, so we preserve both bookends.
    """
    words = text.split()
    if len(words) <= max_words:
        return text
    head_size = 1000
    tail_size = max_words - head_size
    head = ' '.join(words[:head_size])
    tail = ' '.join(words[-tail_size:])
    return head + '\n\n[... transcript truncated ...]\n\n' + tail


def fetch_transcript(video_id):
    """Fetch the transcript for a YouTube video using youtube-transcript-api."""
    api = YouTubeTranscriptApi()
    transcript = api.fetch(video_id)
    text = ' '.join(snippet.text for snippet in transcript)
    return text


def _call_with_retry(fn, max_retries=5):
    """Call fn(), retrying on rate-limit errors with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return fn()
        except anthropic.RateLimitError as e:
            if attempt < max_retries - 1:
                wait = min(2 ** attempt * 10, 120)
                log.warning("Rate limited. Waiting %ds before retry %d/%d...",
                            wait, attempt + 1, max_retries)
                time.sleep(wait)
            else:
                raise
        except anthropic.APIStatusError as e:
            if e.status_code == 529:  # overloaded
                if attempt < max_retries - 1:
                    wait = min(2 ** attempt * 10, 120)
                    log.warning("API overloaded (529). Waiting %ds before retry %d/%d...",
                                wait, attempt + 1, max_retries)
                    time.sleep(wait)
                else:
                    raise
            else:
                raise


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


def extract_with_claude(client, title, transcript_text):
    """Send the transcript + title to Claude for structured extraction."""
    prompt = (
        f"Video title: {title}\n\n"
        f"Transcript:\n{transcript_text}\n\n"
        f"{EXTRACTION_PROMPT}\n"
        "Return ONLY the JSON object, no markdown fences or extra text."
    )

    def _call():
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=16384,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3].strip()
        return text

    return _call_with_retry(_call)


def prefilter_pending(conn, limit=None):
    """Use a cheap text-only LLM call to reject non-candidate videos."""
    if not PREFILTER_ENABLED:
        log.info("Pre-filter disabled, skipping.")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("Set ANTHROPIC_API_KEY to run pre-filter.")
        return

    client = anthropic.Anthropic(api_key=api_key)
    c = conn.cursor()

    query = "SELECT video_id, title, description_snippet FROM videos WHERE status = 'PENDING'"
    if limit:
        query += f" LIMIT {int(limit)}"
    c.execute(query)
    rows = c.fetchall()

    if not rows:
        log.info("No PENDING videos to pre-filter.")
        return

    log.info("Pre-filtering %d PENDING videos...", len(rows))
    for idx, (vid_id, title, desc) in enumerate(rows):
        prompt = PREFILTER_PROMPT.format(
            title=title,
            description=desc or '(no description available)',
        )
        try:
            def _call(p=prompt):
                return client.messages.create(
                    model=PREFILTER_MODEL,
                    max_tokens=256,
                    messages=[{"role": "user", "content": p}],
                )
            response = _call_with_retry(_call)
            answer = response.content[0].text.strip()
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

        time.sleep(1)


def process_pending(conn, retry_failed=False, limit=None):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("Set ANTHROPIC_API_KEY environment variable to run LLM extraction.")
        return

    client = anthropic.Anthropic(api_key=api_key)
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
            transcript_text = trim_transcript(transcript_text, MAX_TRANSCRIPT_WORDS)
        except Exception as e:
            log.warning(" -> Transcript fetch failed for %s: %s", title, e)
            c.execute(
                "UPDATE videos SET status = 'FAILED_TRANSCRIPT', error_msg = ? WHERE video_id = ?",
                (str(e), vid_id),
            )
            conn.commit()
            continue

        # Step 2: Send transcript to Claude for extraction
        try:
            llm_result_str = extract_with_claude(client, title, transcript_text)
            llm_data = json.loads(llm_result_str)

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

    conn = setup_db()
    fetch_candidates(conn, limit=limit)
    prefilter_pending(conn, limit=limit)
    process_pending(conn, retry_failed=retry_failed, limit=limit)
    export_to_jsonl(conn)
    print_status(conn)


if __name__ == "__main__":
    main()
