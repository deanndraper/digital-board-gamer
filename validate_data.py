import pandas as pd
import scrapetube
from fuzzywuzzy import fuzz
import re

from config import CHANNELS, SPREADSHEET_FILE


def clean_title(title):
    title = re.sub(r'(?i)\b(review|how to play|top \d+|playthrough|unboxing|tutorial|setup)\b', '', title)
    title = re.sub(r'[^\w\s]', '', title)
    return title.strip().lower()


def main():
    print("Loading existing spreadsheet data...")
    df = pd.read_excel(SPREADSHEET_FILE)

    if 'Game Title' in df.columns:
        existing_games = df['Game Title'].dropna().tolist()
    else:
        existing_games = df.iloc[:, 1].dropna().tolist()

    existing_games_clean = [clean_title(str(g)) for g in existing_games]
    print(f"Loaded {len(existing_games)} games from spreadsheet.")

    missing_reports = []

    for channel_name, url in CHANNELS.items():
        print(f"\nFetching videos for {channel_name}...")
        try:
            videos = scrapetube.get_channel(channel_url=url)
            count = 0
            for video in videos:
                if count >= 100:
                    break
                count += 1

                vid_title = video.get('title', {}).get('runs', [{}])[0].get('text', '')
                if not vid_title:
                    continue

                vid_title_clean = clean_title(vid_title)

                best_match = None
                best_score = 0
                for game, game_clean in zip(existing_games, existing_games_clean):
                    if len(game_clean) < 3:
                        continue

                    if game_clean in vid_title_clean:
                        best_score = 100
                        best_match = game
                        break

                    score = fuzz.partial_ratio(game_clean, vid_title_clean)
                    if score > best_score:
                        best_score = score
                        best_match = game

                if best_score < 85:
                    missing_reports.append({
                        'Channel': channel_name,
                        'Video Title': vid_title,
                        'Best Match Attempt': best_match,
                        'Match Score': best_score,
                    })
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"Error fetching {channel_name}: {e}")

    print("\n--- MISSING GAMES REPORT ---")
    report_df = pd.DataFrame(missing_reports)
    if not report_df.empty:
        print(f"Found {len(report_df)} videos that potentially feature missing games.")
        report_df.to_csv('missing_games_report.csv', index=False)
        print("Detailed report saved to 'missing_games_report.csv'.")
    else:
        print("No missing games found!")


if __name__ == "__main__":
    main()
