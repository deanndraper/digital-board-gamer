"""Smoke test: fetch a YouTube transcript and send it to Claude for analysis."""
import os
import re

import anthropic
from youtube_transcript_api import YouTubeTranscriptApi

from config import LLM_MODEL, TEST_VIDEO_URL, TEST_PROMPT

# Extract video ID from URL
match = re.search(r'[?&]v=([^&]+)', TEST_VIDEO_URL)
video_id = match.group(1) if match else TEST_VIDEO_URL

print(f"Fetching transcript for {video_id}...")
api = YouTubeTranscriptApi()
transcript = api.fetch(video_id)
text = ' '.join(snippet.text for snippet in transcript)
print(f"Transcript length: {len(text.split())} words")

print(f"\nSending to Claude ({LLM_MODEL})...")
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
response = client.messages.create(
    model=LLM_MODEL,
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": f"Video transcript:\n{text}\n\n{TEST_PROMPT}",
    }],
)
print(response.content[0].text)
