"""Smoke test: verify Gemini can process a YouTube URL directly."""
import os
from google import genai
from google.genai import types

from config import GEMINI_MODEL, TEST_VIDEO_URL, TEST_PROMPT

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
response = client.models.generate_content(
    model=GEMINI_MODEL,
    contents=types.Content(
        parts=[
            types.Part(
                file_data=types.FileData(
                    file_uri=TEST_VIDEO_URL,
                ),
            ),
            types.Part(text=TEST_PROMPT),
        ],
    ),
)
print(response.text)
