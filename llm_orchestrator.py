import sqlite3
import json
import re
import os
import time
from datetime import datetime
import scrapetube
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from google import genai
from google.genai import types

CHANNELS = {
    'Digital Board Gamer': 'https://www.youtube.com/@DigitalBoardGamer',
    'Game-Night with Saisha': 'https://www.youtube.com/@GameNightwithSaisha',
    'Peaky Boardgamer': 'https://www.youtube.com/@PeakyBoardgamer'
}

DB_NAME = 'orchestrator_state.db'

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
    print("Fetching video candidates from channels...")
    c = conn.cursor()
    for channel, url in CHANNELS.items():
        print(f"Scraping {channel}...")
        try:
            videos = scrapetube.get_channel(channel_url=url)
            count = 0
            for video in videos:
                if count >= 50: # limit to 50 videos per channel
                    break
                
                vid_id = video.get('videoId')
                if not vid_id:
                    continue
                count += 1
                
                # Check if already in DB
                c.execute("SELECT video_id FROM videos WHERE video_id = ?", (vid_id,))
                if c.fetchone():
                    continue

                title = video.get('title', {}).get('runs', [{}])[0].get('text', 'Unknown Title')
                vid_url = f"https://www.youtube.com/watch?v={vid_id}"
                
                # Pre-filter out non-game stuff
                status = 'PENDING'
                lower_title = title.lower()
                if 'channel update' in lower_title or 'vlog' in lower_title or 'q&a' in lower_title:
                    status = 'SKIPPED_BY_FILTER'
                    
                c.execute('''
                    INSERT INTO videos (video_id, title, url, channel, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (vid_id, title, vid_url, channel, status))
            conn.commit()
        except Exception as e:
            print(f"Error fetching {channel}: {e}")

def get_transcript(video_id):
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        transcript = transcript_list.find_transcript(['en', 'en-GB', 'en-US', 'en-CA', 'en-AU', 'en-IN'])
        transcript_data = transcript.fetch()
        formatter = TextFormatter()
        text = formatter.format_transcript(transcript_data)
        return text
    except Exception as e:
        return f"ERROR: {e}"

def extract_with_llm(client, video_title, transcript):
    prompt = f"""
    You are an AI tasked with analyzing a board game YouTube video transcript.
    Video Title: {video_title}
    
    Transcript Snippet (truncated if too long):
    {transcript[:8000]}
    
    Extract the following data points into a strictly formatted JSON object:
    1. A list of games covered in the video. For each game, extract:
       - "title": The name of the game.
       - "ranking": The numerical ranking given to the game in this video (e.g. 1 if it is their #1 game of the year). Use null if no rank is given.
       - "score": The numeric score given to the game if provided, else null.
       - "opinion": A brief summary of the reviewer's subjective opinion of this specific game.
    2. A brief summary of the overall video. (string)
    3. Classification (Choose one: 'best of year', 'how to play', 'new game including how to play', 'new game including how to play and rating', 'review', 'playthrough', 'other'). (string)
    4. The link to the video. (leave null, we handle this)
    5. Date the video was published. (leave null, we handle this)
    6. Channel of the video. (leave null, we handle this)

    Return ONLY a JSON object matching this schema precisely:
    {{
        "games": [
            {{
                "title": "Game Name",
                "ranking": 1,
                "score": 9.5,
                "opinion": "absolutely fantastic mechanics."
            }}
        ],
        "summary": "...",
        "classification": "..."
    }}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    return response.text

def process_pending(conn):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Set GEMINI_API_KEY in environment variables to run LLM extraction.")
        return

    client = genai.Client(api_key=api_key)
    c = conn.cursor()
    c.execute("SELECT video_id, title, url, channel FROM videos WHERE status = 'PENDING'")
    rows = c.fetchall()
    
    print(f"Found {len(rows)} pending videos to process.")
    for idx, (vid_id, title, url, channel) in enumerate(rows):
        print(f"[{idx+1}/{len(rows)}] Processing: {title}")
        
        transcript = get_transcript(vid_id)
        if transcript.startswith("ERROR:"):
            print(f" -> No transcript fetched: {transcript}")
            c.execute("UPDATE videos SET status = 'FAILED_TRANSCRIPT', error_msg = ? WHERE video_id = ?", (transcript, vid_id))
            conn.commit()
            continue
            
        try:
            llm_result_str = extract_with_llm(client, title, transcript)
            # Parse the JSON just to validate it
            llm_data = json.loads(llm_result_str)
            
            # Inject our known metadata
            llm_data['video_link'] = url
            llm_data['channel'] = channel
            # published_date omitted for now, need youtube api key or scraping html for exact date, which scrapetube skips easily.
            # We can use scrapetube's relative time, but skipping for absolute correctness unless needed.
            
            c.execute("UPDATE videos SET status = 'COMPLETED', extracted_data = ? WHERE video_id = ?", (json.dumps(llm_data), vid_id))
            conn.commit()
            print(" -> Extraction Successful!")
        except Exception as e:
            print(f" -> LLM parsing failed: {e}")
            c.execute("UPDATE videos SET status = 'FAILED_LLM', error_msg = ? WHERE video_id = ?", (str(e), vid_id))
            conn.commit()
            
        time.sleep(2) # rate limiting

def export_to_jsonl(conn):
    c = conn.cursor()
    c.execute("SELECT title, url, channel, extracted_data FROM videos WHERE status = 'COMPLETED'")
    rows = c.fetchall()
    
    if not rows:
        print("No completed records found.")
        return
        
    output_file = "Complete_Insights.jsonl"
    print(f"Exporting {len(rows)} records to {output_file}")
    with open(output_file, "w") as f:
        for title, url, channel, data in rows:
            entry = json.loads(data)
            entry['_vid_title'] = title 
            f.write(json.dumps(entry) + '\n')
            
def main():
    conn = setup_db()
    fetch_candidates(conn)
    process_pending(conn)
    export_to_jsonl(conn)

if __name__ == "__main__":
    main()
