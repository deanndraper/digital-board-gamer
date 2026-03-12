import sqlite3
import json
import os
import sys
import time
import logging
from datetime import datetime

import scrapetube
from google import genai
from google.genai import types

from config import (
    CHANNELS, DB_NAME, GEMINI_MODEL, VIDEOS_PER_CHANNEL, RATE_LIMIT_SECONDS,
    SKIP_VIDEO_IDS, SKIP_TITLE_KEYWORDS,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('orchestrator.log'),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are an AI tasked with analyzing a board game YouTube video.

Extract the following data points into a strictly formatted JSON object:
1. A list of games covered in the video. For each game, extract:
   - "title": The name of the game.
   - "ranking": The numerical ranking given to the game in this video (e.g. 1 if it is their #1 game). Use null if no rank is given.
   - "score": The reviewer's personal numeric rating for the game (e.g. 7/10, 8.5/10). Use null if no personal rating is given. IMPORTANT: Do NOT put vote percentages, poll results, or community vote shares here — only the reviewer's own score out of 10.
   - "vote_percentage": If the video is about awards or polls, the percentage of votes this game received. Use null otherwise.
   - "award_category": If the game won or was nominated in an award category, the category name (e.g. "Best Casual Game"). Use null otherwise.
   - "opinion": A brief summary of the reviewer's subjective opinion of this specific game.
2. "summary": A brief summary of the overall video. (string)
3. "classification": Choose one of: 'best of year', 'how to play', 'new game including how to play', 'new game including how to play and rating', 'review', 'playthrough', 'other'. (string)

Return ONLY a JSON object matching this schema precisely:
{
    "games": [
        {
            "title": "Game Name",
            "ranking": 1,
            "score": 9.5,
            "vote_percentage": null,
            "award_category": null,
            "opinion": "absolutely fantastic mechanics."
        }
    ],
    "summary": "...",
    "classification": "..."
}
"""


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
    return conn


def fetch_candidates(conn):
    log.info("Fetching video candidates from channels...")
    c = conn.cursor()
    for channel, url in CHANNELS.items():
        log.info("Scraping %s...", channel)
        try:
            videos = scrapetube.get_channel(channel_url=url)
            count = 0
            for video in videos:
                if count >= VIDEOS_PER_CHANNEL:
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

                # Extract published date from scrapetube metadata
                published_text = video.get('publishedTimeText', {}).get('simpleText', '')

                # Skip known off-topic videos by ID or generic title keywords
                status = 'PENDING'
                if vid_id in SKIP_VIDEO_IDS:
                    status = 'SKIPPED_BY_FILTER'
                elif any(kw in title.lower() for kw in SKIP_TITLE_KEYWORDS):
                    status = 'SKIPPED_BY_FILTER'

                c.execute('''
                    INSERT INTO videos (video_id, title, url, channel, status, published_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (vid_id, title, vid_url, channel, status, published_text))
            conn.commit()
        except KeyboardInterrupt:
            raise
        except Exception:
            log.exception("Error fetching %s", channel)


def extract_with_gemini(client, video_url):
    """Send the YouTube URL directly to Gemini for analysis — no transcript API needed."""
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=types.Content(
            parts=[
                types.Part(
                    file_data=types.FileData(file_uri=video_url),
                ),
                types.Part(text=EXTRACTION_PROMPT),
            ],
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    return response.text


def process_pending(conn, retry_failed=False, limit=None):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.error("Set GEMINI_API_KEY environment variable to run LLM extraction.")
        return

    client = genai.Client(api_key=api_key)
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

        try:
            llm_result_str = extract_with_gemini(client, url)
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

    output_file = "Complete_Insights.jsonl"
    log.info("Exporting %d records to %s", len(rows), output_file)
    with open(output_file, "w") as f:
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
    fetch_candidates(conn)
    process_pending(conn, retry_failed=retry_failed, limit=limit)
    export_to_jsonl(conn)
    print_status(conn)


if __name__ == "__main__":
    main()
