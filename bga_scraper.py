#!/usr/bin/env python3
"""Scrape Board Game Arena for the most popular games and their metadata."""

import sqlite3
import json
import os
import re
import sys
import time
import logging
from datetime import datetime, timezone

import requests
import yaml
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_config_path = os.environ.get("BGA_CONFIG", "bga_config.yaml")
with open(_config_path) as f:
    _cfg = yaml.safe_load(f)["bga"]

GAMELIST_URL = _cfg["gamelist_url"]
GAMEPANEL_URL = _cfg["gamepanel_url"]
TOP_N = _cfg["top_n_games"]
RATE_LIMIT = _cfg["rate_limit_seconds"]
DB_NAME = _cfg["db_name"]
OUTPUT_JSONL = _cfg["output_jsonl"]
LOG_FILE = _cfg["log_file"]
USER_AGENT = _cfg["user_agent"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def setup_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bga_games (
            game_id TEXT PRIMARY KEY,
            name TEXT,
            url TEXT,
            popularity_rank INTEGER,
            games_played INTEGER,
            games_played_recent INTEGER,
            weight REAL,
            audience_trend REAL,
            bgg_id INTEGER,
            premium INTEGER,
            has_tutorial INTEGER,
            player_numbers TEXT,
            average_duration INTEGER,
            realtime TEXT,
            turnbased TEXT,
            league_number INTEGER,
            arena_num_players INTEGER,
            default_num_players INTEGER,
            published_on TEXT,
            tags TEXT,
            list_data TEXT,
            status TEXT DEFAULT 'PENDING',
            game_data TEXT,
            error_msg TEXT,
            scraped_at TEXT
        )
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Phase 1: Fetch game list
# ---------------------------------------------------------------------------
def _extract_json_array(html, key):
    """Extract a JSON array from HTML by finding "key":[...] pattern."""
    marker = f'"{key}":['
    idx = html.find(marker)
    if idx < 0:
        return None
    arr_start = html.index("[", idx)
    depth = 0
    for end in range(arr_start, len(html)):
        if html[end] == "[":
            depth += 1
        elif html[end] == "]":
            depth -= 1
            if depth == 0:
                return json.loads(html[arr_start : end + 1])
    return None


def fetch_game_list(conn, top_n=TOP_N):
    """Fetch the BGA game list and insert the top N games into the DB."""
    log.info("Fetching BGA game list from %s", GAMELIST_URL)
    resp = SESSION.get(GAMELIST_URL, timeout=30)
    resp.raise_for_status()
    html = resp.text

    games = _extract_json_array(html, "game_list")
    if not games:
        log.error("Could not find game_list in BGA page")
        return

    # Build tag ID -> name mapping from game_tags
    tag_list = _extract_json_array(html, "game_tags") or []
    tag_map = {t["id"]: t for t in tag_list}
    log.info("Found %d total games and %d tag definitions on BGA", len(games), len(tag_map))

    # Sort by all-time games played, descending
    games.sort(key=lambda g: int(g.get("games_played", 0) or 0), reverse=True)
    top_games = games[:top_n]

    c = conn.cursor()
    inserted = 0
    for rank, g in enumerate(top_games, 1):
        game_id = g["name"]
        display_name = g.get("display_name_en", game_id)
        url = GAMEPANEL_URL.format(game_id=game_id)

        # Resolve tag IDs to names, grouped by category
        tags_resolved = []
        for tag_id, _weight in g.get("tags", []):
            tag_info = tag_map.get(tag_id)
            if tag_info and tag_info.get("cat") not in ("Admin", ""):
                tags_resolved.append({
                    "name": tag_info["name"],
                    "category": tag_info.get("cat", ""),
                })

        try:
            c.execute(
                """INSERT OR IGNORE INTO bga_games
                   (game_id, name, url, popularity_rank, games_played,
                    games_played_recent, weight, audience_trend, bgg_id,
                    premium, has_tutorial, player_numbers, average_duration,
                    realtime, turnbased, league_number, arena_num_players,
                    default_num_players, published_on, tags, list_data, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')""",
                (
                    game_id,
                    display_name,
                    url,
                    rank,
                    int(g.get("games_played", 0) or 0),
                    int(g.get("games_played_recent", 0) or 0),
                    float(g.get("weight", 0) or 0),
                    float(g.get("audience_trend", 0) or 0),
                    g.get("bgg_id"),
                    1 if g.get("premium") else 0,
                    1 if g.get("has_tutorial") else 0,
                    json.dumps(g.get("player_numbers", [])),
                    g.get("average_duration"),
                    g.get("realtime", ""),
                    g.get("turnbased", ""),
                    g.get("league_number"),
                    g.get("arena_num_players"),
                    g.get("default_num_players"),
                    g.get("published_on", ""),
                    json.dumps(tags_resolved),
                    json.dumps({
                        k: v for k, v in g.items()
                        if k not in ("media", "last_options", "prefs_string",
                                     "last_prefs_string", "saved_prefs_strings")
                    }),
                ),
            )
            if c.rowcount > 0:
                inserted += 1
        except Exception:
            log.exception("Error inserting %s", game_id)

    conn.commit()
    log.info("Inserted %d new games (top %d by games played)", inserted, top_n)


# ---------------------------------------------------------------------------
# Phase 2: Scrape individual game pages
# ---------------------------------------------------------------------------
def _parse_row_data(soup):
    """Extract key-value pairs from the row-data divs on a game panel page."""
    data = {}
    for row in soup.find_all("div", class_="row-data"):
        text = row.get_text(separator="|", strip=True)
        # row-data contains label + value, e.g. "Designer|Klaus Teuber"
        parts = text.split("|", 1)
        if len(parts) == 2:
            key = parts[0].strip().lower().replace(" ", "_")
            val = parts[1].strip()
            data[key] = val
    return data


def _clean_number(s):
    """Parse a number string like '7 390 746' into an int."""
    if not s:
        return None
    cleaned = re.sub(r"[^\d]", "", s)
    return int(cleaned) if cleaned else None


def _parse_player_range(s):
    """Parse '3 - 4' into (3, 4)."""
    if not s:
        return None, None
    m = re.match(r"(\d+)\s*-\s*(\d+)", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"(\d+)", s)
    if m:
        return int(m.group(1)), int(m.group(1))
    return None, None


def _parse_duration(s):
    """Parse '36 mn' into 36."""
    if not s:
        return None
    m = re.match(r"(\d+)", s)
    return int(m.group(1)) if m else None


def _find_box_image(soup, game_id):
    """Find the box art image URL from the game page."""
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "/box/" in src and "gamemedia" in src:
            return src.split("?")[0]  # strip cache-buster param
    # Fallback: construct from known pattern
    return f"https://x.boardgamearena.net/data/gamemedia/{game_id}/box/en_280.png"


def scrape_game(game_id, url):
    """Scrape a single game's detail page and return structured data."""
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    raw = _parse_row_data(soup)

    min_p, max_p = _parse_player_range(raw.get("number_of_players"))

    return {
        "game_id": game_id,
        "designer": raw.get("designer"),
        "artist": raw.get("artist"),
        "publisher": (raw.get("publisher") or "").rstrip("|- ").strip() or None,
        "year_published": _clean_number(raw.get("year")),
        "developed_by": raw.get("developed_by"),
        "maintained_by": raw.get("maintained_by") or None,
        "total_games_played": _clean_number(raw.get("number_of_games_played")),
        "min_players": min_p,
        "max_players": max_p,
        "avg_duration_minutes": _parse_duration(raw.get("game_duration")),
        "complexity": _clean_number(raw.get("complexity")),
        "strategy": _clean_number(raw.get("strategy")),
        "luck": _clean_number(raw.get("luck")),
        "interaction": _clean_number(raw.get("interaction")),
        "available_since": raw.get("available_since"),
        "release": raw.get("release"),
        "box_image_url": _find_box_image(soup, game_id),
    }


def process_pending(conn, retry_failed=False, limit=None):
    """Scrape all PENDING (and optionally FAILED) games."""
    c = conn.cursor()

    statuses = ["PENDING"]
    if retry_failed:
        statuses.append("FAILED")

    placeholders = ",".join("?" for _ in statuses)
    query = f"SELECT game_id, name, url FROM bga_games WHERE status IN ({placeholders}) ORDER BY popularity_rank"
    if limit:
        query += f" LIMIT {limit}"

    c.execute(query, statuses)
    rows = c.fetchall()

    if not rows:
        log.info("No games to process.")
        return

    log.info("Processing %d games...", len(rows))

    for idx, (game_id, name, url) in enumerate(rows):
        log.info("[%d/%d] Scraping: %s", idx + 1, len(rows), name)

        try:
            game_data = scrape_game(game_id, url)
            now = datetime.now(timezone.utc).isoformat()

            c.execute(
                """UPDATE bga_games
                   SET status = 'COMPLETED', game_data = ?, error_msg = NULL, scraped_at = ?
                   WHERE game_id = ?""",
                (json.dumps(game_data), now, game_id),
            )
            conn.commit()
            log.info("  -> Success")

        except KeyboardInterrupt:
            raise
        except Exception as e:
            log.warning("  -> Failed: %s", e)
            c.execute(
                "UPDATE bga_games SET status = 'FAILED', error_msg = ? WHERE game_id = ?",
                (str(e), game_id),
            )
            conn.commit()

        if idx < len(rows) - 1:
            time.sleep(RATE_LIMIT)


# ---------------------------------------------------------------------------
# Phase 3: Export
# ---------------------------------------------------------------------------
def export_to_jsonl(conn):
    """Export all COMPLETED games to a JSONL file."""
    c = conn.cursor()
    c.execute(
        """SELECT game_id, name, url, popularity_rank, games_played,
                  games_played_recent, weight, audience_trend, bgg_id,
                  premium, has_tutorial, player_numbers, average_duration,
                  realtime, turnbased, league_number, arena_num_players,
                  default_num_players, published_on, tags, game_data, scraped_at
           FROM bga_games WHERE status = 'COMPLETED' ORDER BY popularity_rank"""
    )
    rows = c.fetchall()

    with open(OUTPUT_JSONL, "w") as f:
        for (game_id, name, url, rank, played, recent, weight, trend, bgg_id,
             premium, has_tutorial, player_numbers, avg_dur, realtime, turnbased,
             league_number, arena_num_players, default_num_players,
             published_on, tags_str, data_str, scraped_at) in rows:
            record = {
                "game_id": game_id,
                "name": name,
                "url": url,
                "bgg_url": f"https://boardgamegeek.com/boardgame/{bgg_id}" if bgg_id else None,
                "popularity_rank": rank,
                "games_played": played,
                "games_played_recent": recent,
                "weight": weight,
                "audience_trend": trend,
                "bgg_id": bgg_id,
                "premium": bool(premium),
                "has_tutorial": bool(has_tutorial),
                "player_numbers": json.loads(player_numbers) if player_numbers else [],
                "average_duration": avg_dur,
                "realtime": realtime or None,
                "turnbased": turnbased or None,
                "league_number": league_number,
                "arena_num_players": arena_num_players,
                "default_num_players": default_num_players,
                "published_on_bga": published_on,
                "tags": json.loads(tags_str) if tags_str else [],
                "scraped_at": scraped_at,
            }
            if data_str:
                record.update(json.loads(data_str))
            f.write(json.dumps(record) + "\n")

    log.info("Exported %d games to %s", len(rows), OUTPUT_JSONL)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
def print_status(conn):
    c = conn.cursor()
    c.execute("SELECT status, COUNT(*) FROM bga_games GROUP BY status ORDER BY status")
    log.info("--- Database Status ---")
    for status, count in c.fetchall():
        log.info("  %s: %d", status, count)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    export_only = "--export-only" in sys.argv
    retry_failed = "--retry" in sys.argv

    limit = None
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])
        elif arg.isdigit():
            limit = int(arg)

    conn = setup_db()

    if export_only:
        export_to_jsonl(conn)
    else:
        fetch_game_list(conn, top_n=TOP_N)
        process_pending(conn, retry_failed=retry_failed, limit=limit)
        export_to_jsonl(conn)

    print_status(conn)
