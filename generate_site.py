#!/usr/bin/env python3
"""Generate a static HTML site from channel_insights_*.jsonl using Tabulator."""

import glob
import json
import os
from datetime import datetime, timezone

JSONL_PATTERN = "channel_insights_*.jsonl"
OUTPUT_DIR = "docs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")


def load_data(pattern):
    """Read all matching JSONL files and return a flat list of game dicts."""
    games = []
    video_titles = set()
    channels = set()

    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matching {pattern}")

    for path in files:
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
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/tabulator-tables@6/dist/css/tabulator_simple.min.css">
    <style>
        :root {
            --bg-dark: #0f172a;
            --bg-card: #1e293b;
            --bg-body: #f1f5f9;
            --accent: #6366f1;
            --accent-light: #818cf8;
            --green: #22c55e;
            --yellow: #eab308;
            --red: #ef4444;
            --text-primary: #1e293b;
            --text-muted: #64748b;
            --text-light: #cbd5e1;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-body);
            color: var(--text-primary);
            min-height: 100vh;
        }

        /* Hero header */
        .hero {
            background: linear-gradient(135deg, var(--bg-dark) 0%, #1e1b4b 50%, #312e81 100%);
            color: #fff;
            padding: 2.5rem 2rem 2rem;
            text-align: center;
        }
        .hero h1 {
            font-size: 2.2rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            margin-bottom: 0.4rem;
        }
        .hero h1 span { color: var(--accent-light); }
        .hero p {
            color: var(--text-light);
            font-size: 1rem;
            font-weight: 400;
            max-width: 600px;
            margin: 0 auto;
        }

        /* Stats bar */
        .stats-bar {
            display: flex;
            justify-content: center;
            gap: 1px;
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            overflow: hidden;
            max-width: 700px;
            margin: 1.5rem auto 0;
        }
        .stats-bar .stat {
            flex: 1;
            padding: 1rem 0.5rem;
            text-align: center;
            background: rgba(255,255,255,0.05);
            transition: background 0.2s;
        }
        .stats-bar .stat:hover { background: rgba(255,255,255,0.1); }
        .stats-bar .stat strong {
            display: block;
            font-size: 1.5rem;
            font-weight: 700;
            color: #fff;
        }
        .stats-bar .stat span {
            font-size: 0.75rem;
            color: var(--text-light);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        /* Main content */
        .content {
            max-width: 1400px;
            margin: 0 auto;
            padding: 1.5rem;
        }

        /* Toolbar */
        .toolbar {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }
        .toolbar button {
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 6px;
            font-family: 'Inter', sans-serif;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
        }
        .btn-primary {
            background: var(--accent);
            color: #fff;
        }
        .btn-primary:hover { background: var(--accent-light); }
        .btn-secondary {
            background: #fff;
            color: var(--text-primary);
            box-shadow: 0 1px 2px rgba(0,0,0,0.08);
        }
        .btn-secondary:hover { background: #f8fafc; }

        /* Table container */
        #game-table {
            background: #fff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 4px 12px rgba(0,0,0,0.04);
        }

        /* Tabulator overrides */
        .tabulator {
            font-family: 'Inter', sans-serif;
            font-size: 0.85rem;
            border: none;
            background: transparent;
        }
        .tabulator .tabulator-header {
            background: var(--bg-dark);
            color: #e2e8f0;
            border-bottom: 2px solid var(--accent);
        }
        .tabulator .tabulator-header .tabulator-col {
            border-right: 1px solid rgba(255,255,255,0.08);
            background: transparent;
        }
        .tabulator .tabulator-header .tabulator-col .tabulator-col-content {
            padding: 10px 12px;
        }
        .tabulator .tabulator-header .tabulator-col .tabulator-col-title {
            font-weight: 600;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #cbd5e1;
        }
        .tabulator .tabulator-header .tabulator-col .tabulator-header-filter {
            padding: 4px 8px 8px;
        }
        .tabulator .tabulator-header .tabulator-col .tabulator-header-filter input,
        .tabulator .tabulator-header .tabulator-col .tabulator-header-filter select {
            width: 100%;
            padding: 5px 8px;
            font-size: 0.78rem;
            font-family: 'Inter', sans-serif;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            background: #fff;
            color: var(--text-primary);
        }
        .tabulator .tabulator-header .tabulator-col .tabulator-header-filter input::placeholder {
            color: #94a3b8;
        }
        .tabulator .tabulator-header .tabulator-col .tabulator-header-filter select option {
            color: var(--text-primary);
            background: #fff;
        }
        .tabulator-row .tabulator-cell {
            padding: 10px 12px;
            border-right: 1px solid #f1f5f9;
            border-bottom: 1px solid #f1f5f9;
        }
        .tabulator-row { background: #fff; }
        .tabulator-row.tabulator-row-even { background: #f8fafc; }
        .tabulator-row:hover { background: #eef2ff !important; }
        .tabulator-row .tabulator-cell[tabulator-field="opinion"] {
            white-space: normal;
            line-height: 1.5;
            color: var(--text-muted);
            font-size: 0.82rem;
        }
        .tabulator-row .tabulator-cell[tabulator-field="video_title"] {
            white-space: normal;
            line-height: 1.4;
        }

        /* Score pill */
        .score-pill {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.82rem;
        }
        .score-high { background: #dcfce7; color: #166534; }
        .score-mid { background: #fef9c3; color: #854d0e; }
        .score-low { background: #fee2e2; color: #991b1b; }

        /* Rank badge */
        .rank-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.8rem;
            background: #e0e7ff;
            color: #3730a3;
        }
        .rank-source {
            display: block;
            font-size: 0.68rem;
            color: var(--text-muted);
            font-weight: 400;
            margin-top: 1px;
        }

        /* Channel tag */
        .channel-tag {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.78rem;
            font-weight: 500;
            background: #f1f5f9;
            color: var(--text-muted);
        }

        /* Video link */
        a.video-link {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            height: 28px;
            border-radius: 6px;
            background: #fee2e2;
            color: #dc2626;
            text-decoration: none;
            font-size: 0.9rem;
            transition: all 0.15s;
        }
        a.video-link:hover { background: #dc2626; color: #fff; }

        /* Footer */
        .tabulator .tabulator-footer {
            background: #f8fafc;
            border-top: 1px solid #e2e8f0;
            font-size: 0.82rem;
            color: var(--text-muted);
        }
        .tabulator .tabulator-footer .tabulator-page {
            border-radius: 4px;
            margin: 0 2px;
        }
        .tabulator .tabulator-footer .tabulator-page.active {
            background: var(--accent);
            color: #fff;
        }
        footer {
            text-align: center;
            font-size: 0.78rem;
            color: var(--text-muted);
            padding: 1.5rem 0;
        }
        footer a { color: var(--accent); text-decoration: none; }
        footer a:hover { text-decoration: underline; }

        /* Responsive */
        @media (max-width: 768px) {
            .hero { padding: 1.5rem 1rem 1.5rem; }
            .hero h1 { font-size: 1.5rem; }
            .stats-bar { flex-wrap: wrap; }
            .stats-bar .stat { min-width: 45%; }
            .content { padding: 1rem; }
        }
    </style>
</head>
<body>
    <div class="hero">
        <h1>Board Game <span>Insights</span></h1>
        <p>Reviews, rankings, and opinions extracted from YouTube board game channels using AI</p>
        <div class="stats-bar">
            <div class="stat"><strong>__UNIQUE_GAMES__</strong><span>Games</span></div>
            <div class="stat"><strong>__VIDEO_COUNT__</strong><span>Videos</span></div>
            <div class="stat"><strong>__CHANNEL_COUNT__</strong><span>Channels</span></div>
            <div class="stat"><strong>__TOTAL_MENTIONS__</strong><span>Mentions</span></div>
        </div>
    </div>

    <div class="content">
        <div class="toolbar">
            <button class="btn-primary" onclick="table.download('csv', 'board_game_insights.csv')">Export CSV</button>
            <button class="btn-secondary" onclick="clearFilters()">Clear Filters</button>
        </div>

        <div id="game-table"></div>
    </div>

    <footer>
        <p>Data extracted by <a href="https://claude.ai">Claude</a> from YouTube transcripts &middot; Updated __TIMESTAMP__</p>
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

        function scoreClass(v) {
            if (v >= 8) return "score-high";
            if (v >= 5) return "score-mid";
            return "score-low";
        }

        var table = new Tabulator("#game-table", {
            data: DATA,
            layout: "fitColumns",
            pagination: true,
            paginationSize: 50,
            paginationSizeSelector: [25, 50, 100, true],
            movableColumns: true,
            placeholder: "No matching games found",
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
                    headerFilterPlaceholder: "Search",
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
                    headerFilterParams: {values: CHANNELS, clearable: true},
                    formatter: function(cell) {
                        return '<span class="channel-tag">' + cell.getValue() + '</span>';
                    }
                },
                {
                    title: "Score",
                    field: "score",
                    width: 85,
                    hozAlign: "center",
                    sorter: "number",
                    headerFilter: "number",
                    headerFilterPlaceholder: "Min",
                    headerFilterFunc: ">=",
                    formatter: function(cell) {
                        var v = cell.getValue();
                        if (v == null) return "";
                        return '<span class="score-pill ' + scoreClass(v) + '">' + v + '/10</span>';
                    }
                },
                {
                    title: "Rank",
                    field: "ranking",
                    width: 90,
                    hozAlign: "center",
                    sorter: "number",
                    formatter: function(cell) {
                        var v = cell.getValue();
                        if (v == null) return "";
                        var src = cell.getRow().getData().ranking_source;
                        var label = RANK_SOURCE_LABELS[src] || "";
                        var html = '<span class="rank-badge">#' + v + '</span>';
                        if (label) html += '<span class="rank-source">' + label + '</span>';
                        return html;
                    }
                },
                {
                    title: "Rank Source",
                    field: "ranking_source",
                    width: 120,
                    visible: false,
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
                    formatter: "plaintext",
                    headerFilter: "input",
                    headerFilterPlaceholder: "Search"
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
                    headerFilterPlaceholder: "Search"
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
    games, video_count, channels = load_data(JSONL_PATTERN)
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
