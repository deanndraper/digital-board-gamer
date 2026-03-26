#!/usr/bin/env python3
"""Generate a static HTML site from Complete_Insights.jsonl using Tabulator."""

import json
import os
from datetime import datetime, timezone

JSONL_PATH = "Complete_Insights.jsonl"
OUTPUT_DIR = "docs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")


def load_data(path):
    """Read JSONL and return a flat list of game dicts with video metadata."""
    games = []
    video_titles = set()
    channels = set()

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            vid_title = record.get("_vid_title", "")
            channel = record.get("channel", "")
            video_titles.add(vid_title)
            channels.add(channel)

            for game in record.get("games", []):
                games.append({
                    "title": game.get("title", ""),
                    "score": game.get("score"),
                    "ranking": game.get("ranking"),
                    "ranking_source": game.get("ranking_source"),
                    "opinion": game.get("opinion", "") or "",
                    "channel": channel,
                    "video_link": record.get("video_link", ""),
                    "video_title": vid_title,
                    "classification": record.get("classification", ""),
                })

    return games, len(video_titles), sorted(channels)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Board Game Insights</title>
    <link rel="stylesheet" href="https://unpkg.com/tabulator-tables@6/dist/css/tabulator_simple.min.css">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            padding: 1.5rem;
        }
        header { text-align: center; margin-bottom: 1.5rem; }
        header h1 { font-size: 1.8rem; margin-bottom: 0.3rem; }
        header p { color: #666; font-size: 0.95rem; }
        .stats {
            display: flex; gap: 1.5rem; justify-content: center;
            flex-wrap: wrap; margin-bottom: 1.5rem;
        }
        .stat {
            background: #fff; border-radius: 8px; padding: 0.8rem 1.5rem;
            text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .stat strong { display: block; font-size: 1.6rem; color: #2563eb; }
        .stat span { font-size: 0.85rem; color: #666; }
        .toolbar { margin-bottom: 0.75rem; }
        .toolbar button {
            padding: 0.4rem 1rem; border: 1px solid #ccc; border-radius: 4px;
            background: #fff; cursor: pointer; font-size: 0.85rem;
        }
        .toolbar button:hover { background: #eee; }
        #game-table { background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        footer { text-align: center; font-size: 0.8rem; color: #999; padding: 1.5rem 0 0.5rem; }

        /* Tabulator overrides for readability */
        .tabulator { font-size: 0.9rem; border: none; }
        .tabulator .tabulator-header { background: #f8f9fa; font-weight: 600; }
        .tabulator .tabulator-header .tabulator-col { border-right: 1px solid #e5e7eb; }
        .tabulator .tabulator-header .tabulator-col .tabulator-col-content {
            padding: 8px 10px;
        }
        .tabulator .tabulator-header .tabulator-col .tabulator-header-filter {
            padding: 4px 8px 8px;
        }
        .tabulator .tabulator-header .tabulator-col .tabulator-header-filter input,
        .tabulator .tabulator-header .tabulator-col .tabulator-header-filter select {
            width: 100%; padding: 4px 6px; font-size: 0.8rem;
            border: 1px solid #d1d5db; border-radius: 3px;
        }
        .tabulator-row .tabulator-cell {
            padding: 6px 10px;
            border-right: 1px solid #f0f0f0;
        }
        .tabulator-row.tabulator-row-even { background: #fafbfc; }
        .tabulator-row .tabulator-cell[tabulator-field="opinion"] { white-space: normal; line-height: 1.4; }
        .tabulator .tabulator-footer { background: #f8f9fa; font-size: 0.85rem; }
        .tabulator .tabulator-footer .tabulator-page.active { background: #2563eb; color: #fff; }
        a.video-link { color: #2563eb; text-decoration: none; font-size: 1.1rem; }
        a.video-link:hover { color: #1d4ed8; }
    </style>
</head>
<body>
    <header>
        <h1>Board Game Insights</h1>
        <p>Game reviews and rankings extracted from YouTube board game channels</p>
    </header>

    <div class="stats">
        <div class="stat"><strong>__UNIQUE_GAMES__</strong><span>Unique Games</span></div>
        <div class="stat"><strong>__VIDEO_COUNT__</strong><span>Videos Analyzed</span></div>
        <div class="stat"><strong>__CHANNEL_COUNT__</strong><span>Channels</span></div>
        <div class="stat"><strong>__TOTAL_MENTIONS__</strong><span>Total Mentions</span></div>
    </div>

    <div class="toolbar">
        <button onclick="table.download('csv', 'board_game_insights.csv')">&#11015; Download CSV</button>
        <button onclick="clearFilters()">&#10006; Clear Filters</button>
    </div>

    <div id="game-table"></div>

    <footer>
        <p>Data extracted by Claude from YouTube transcripts &middot; Last updated: __TIMESTAMP__</p>
    </footer>

    <script src="https://unpkg.com/tabulator-tables@6/dist/js/tabulator.min.js"></script>
    <script>
        var DATA = __TABLE_DATA__;
        var CHANNELS = __CHANNEL_VALUES__;
        var CLASSIFICATIONS = __CLASSIFICATION_VALUES__;

        var RANK_SOURCE_LABELS = {
            "personal": "Personal",
            "bga_popularity_yearly": "BGA Yearly",
            "bga_popularity_alltime": "BGA All-Time",
            "community_poll": "Community"
        };

        var RANK_SOURCE_VALUES = {
            "personal": "Personal",
            "bga_popularity_yearly": "BGA Yearly",
            "bga_popularity_alltime": "BGA All-Time",
            "community_poll": "Community"
        };

        var table = new Tabulator("#game-table", {
            data: DATA,
            layout: "fitColumns",
            pagination: true,
            paginationSize: 50,
            paginationSizeSelector: [25, 50, 100, true],
            movableColumns: true,
            placeholder: "No matching games found.",
            initialSort: [
                {column: "title", dir: "asc"}
            ],
            columns: [
                {
                    title: "Game",
                    field: "title",
                    widthGrow: 2,
                    minWidth: 160,
                    headerFilter: "input",
                    headerFilterPlaceholder: "Search...",
                    formatter: function(cell) {
                        return "<strong>" + cell.getValue() + "</strong>";
                    }
                },
                {
                    title: "Channel",
                    field: "channel",
                    widthGrow: 1,
                    minWidth: 130,
                    headerFilter: "list",
                    headerFilterParams: {values: CHANNELS, clearable: true}
                },
                {
                    title: "Score",
                    field: "score",
                    width: 80,
                    hozAlign: "center",
                    sorter: "number",
                    headerFilter: "number",
                    headerFilterPlaceholder: "Min",
                    headerFilterFunc: ">=",
                    formatter: function(cell) {
                        var v = cell.getValue();
                        return v != null ? v + "/10" : "";
                    }
                },
                {
                    title: "Rank",
                    field: "ranking",
                    width: 70,
                    hozAlign: "center",
                    sorter: "number",
                    formatter: function(cell) {
                        var v = cell.getValue();
                        return v != null ? "#" + v : "";
                    }
                },
                {
                    title: "Rank Source",
                    field: "ranking_source",
                    width: 120,
                    headerFilter: "list",
                    headerFilterParams: {values: RANK_SOURCE_VALUES, clearable: true},
                    formatter: function(cell) {
                        var v = cell.getValue();
                        return RANK_SOURCE_LABELS[v] || "";
                    }
                },
                {
                    title: "Type",
                    field: "classification",
                    width: 130,
                    headerFilter: "list",
                    headerFilterParams: {values: CLASSIFICATIONS, clearable: true}
                },
                {
                    title: "Opinion",
                    field: "opinion",
                    widthGrow: 3,
                    minWidth: 200,
                    formatter: "textarea",
                    headerFilter: "input",
                    headerFilterPlaceholder: "Search..."
                },
                {
                    title: "",
                    field: "video_link",
                    width: 50,
                    hozAlign: "center",
                    headerSort: false,
                    formatter: function(cell) {
                        var url = cell.getValue();
                        var vt = cell.getRow().getData().video_title || "";
                        if (url) {
                            return '<a class="video-link" href="' + url + '" target="_blank" title="' + vt.replace(/"/g, '&quot;') + '">&#9654;</a>';
                        }
                        return "";
                    }
                },
                {
                    title: "Source Video",
                    field: "video_title",
                    widthGrow: 2,
                    minWidth: 180,
                    headerFilter: "input",
                    headerFilterPlaceholder: "Search..."
                }
            ]
        });

        function clearFilters() {
            table.clearHeaderFilter();
        }
    </script>
</body>
</html>"""


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    games, video_count, channels = load_data(JSONL_PATH)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    unique_titles = len({g["title"].lower() for g in games})

    channel_values = {ch: ch for ch in channels}
    classification_values = sorted({g["classification"] for g in games if g["classification"]})

    html = HTML_TEMPLATE
    html = html.replace("__UNIQUE_GAMES__", str(unique_titles))
    html = html.replace("__VIDEO_COUNT__", str(video_count))
    html = html.replace("__CHANNEL_COUNT__", str(len(channels)))
    html = html.replace("__TOTAL_MENTIONS__", str(len(games)))
    html = html.replace("__TIMESTAMP__", now)
    html = html.replace("__TABLE_DATA__", json.dumps(games))
    html = html.replace("__CHANNEL_VALUES__", json.dumps(channel_values))
    html = html.replace("__CLASSIFICATION_VALUES__", json.dumps({v: v for v in classification_values}))

    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    print(f"Generated {OUTPUT_FILE} — {len(games)} game mentions from {video_count} videos")


if __name__ == "__main__":
    main()
