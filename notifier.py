#!/usr/bin/env python3
"""Send notifications when new game videos are detected.

Standalone module — imported by llm_orchestrator.py but has no
dependencies on the rest of the pipeline. Easy to swap notification
backends without touching the orchestrator.

Configuration via environment variable or direct call:
    NOTIFY_IMESSAGE_TO="+15551234567"  or  "user@icloud.com"
"""

import logging
import os
import subprocess

log = logging.getLogger(__name__)

# iMessage recipient — phone number or iCloud email
IMESSAGE_TO = os.environ.get("NOTIFY_IMESSAGE_TO", "")


def send_imessage(message, recipient=None):
    """Send an iMessage via AppleScript. macOS only."""
    to = recipient or IMESSAGE_TO
    if not to:
        log.warning("No iMessage recipient configured. Set NOTIFY_IMESSAGE_TO.")
        return False

    # Escape for AppleScript
    escaped = message.replace("\\", "\\\\").replace('"', '\\"')

    script = (
        f'tell application "Messages"\n'
        f'  send "{escaped}" to buddy "{to}" of '
        f'(1st account whose service type = iMessage)\n'
        f'end tell'
    )

    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15,
        )
        log.info("iMessage sent to %s", to)
        return True
    except Exception as e:
        log.warning("Failed to send iMessage: %s", e)
        return False


def notify_new_extractions(new_videos, site_url="https://games.transformativehelp.com/"):
    """Send a notification summarizing newly extracted videos.

    Args:
        new_videos: list of dicts with keys: title, channel, games (list of game dicts)
        site_url: link to the published site
    """
    if not new_videos:
        return

    total_games = sum(len(v.get("games", [])) for v in new_videos)
    total_videos = len(new_videos)

    lines = [f"🎲 {total_games} new games from {total_videos} video{'s' if total_videos != 1 else ''}:"]
    lines.append("")

    for video in new_videos:
        lines.append(f"📺 {video['channel']}: {video['title']}")
        for game in video.get("games", []):
            name = game.get("title", "Unknown")
            score = game.get("score")
            score_str = f" ({score}/10)" if score is not None else ""
            lines.append(f"  • {name}{score_str}")
        lines.append("")

    lines.append(site_url)

    message = "\n".join(lines)
    send_imessage(message)
