"""Smoke test: fetch a YouTube transcript and send it to Claude CLI for analysis."""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi

from config import CLI_COMMAND, CLI_FLAGS, EXTRACTION_INSTRUCTIONS_FILE, TEST_VIDEO_URL

PROJECT_ROOT = Path(__file__).resolve().parent

# Extract video ID from URL
match = re.search(r'[?&]v=([^&]+)', TEST_VIDEO_URL)
video_id = match.group(1) if match else TEST_VIDEO_URL

print(f"Fetching transcript for {video_id}...")
api = YouTubeTranscriptApi()
transcript = api.fetch(video_id)
text = ' '.join(snippet.text for snippet in transcript)
print(f"Transcript length: {len(text.split())} words")

# Set up isolated CLI workspace
workspace = tempfile.mkdtemp(prefix='cli_test_')
try:
    # Minimal CLAUDE.md
    (Path(workspace) / 'CLAUDE.md').write_text(
        "Follow the instruction file exactly. Return only JSON.\n"
    )
    # Copy instruction file
    shutil.copy2(PROJECT_ROOT / EXTRACTION_INSTRUCTIONS_FILE, workspace)

    input_text = f"Video title: test video\n\nTranscript:\n{text}"

    cmd = [CLI_COMMAND, '-p']
    if CLI_FLAGS:
        cmd.extend(CLI_FLAGS.split())
    cmd.extend([
        '--append-system-prompt-file', EXTRACTION_INSTRUCTIONS_FILE,
        '--output-format', 'json',
    ])

    print(f"\nSending to Claude CLI ({CLI_COMMAND})...")
    result = subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        cwd=workspace,
        timeout=300,
    )

    if result.returncode != 0:
        print(f"CLI ERROR (exit {result.returncode}):\n{result.stderr}")
    else:
        raw = result.stdout.strip()
        try:
            parsed = json.loads(raw)
            # Try to unwrap the envelope
            if isinstance(parsed, dict) and 'result' in parsed:
                inner = parsed['result']
                if isinstance(inner, str):
                    inner = json.loads(inner)
                print(json.dumps(inner, indent=2))
            else:
                print(json.dumps(parsed, indent=2))
        except json.JSONDecodeError:
            print("Raw output (not valid JSON):")
            print(raw)
finally:
    shutil.rmtree(workspace, ignore_errors=True)
