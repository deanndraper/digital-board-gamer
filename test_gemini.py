"""Smoke test: verify Gemini can process a YouTube URL directly."""
import os
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=types.Content(
        parts=[
            types.Part(
                file_data=types.FileData(
                    file_uri='https://www.youtube.com/watch?v=EjVvUkZHAes',
                ),
            ),
            types.Part(text='What board game is discussed in this video? Reply in one sentence.'),
        ],
    ),
)
print(response.text)
