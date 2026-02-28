import pandas as pd
import scrapetube
from fuzzywuzzy import fuzz
import re

SPREADSHEET_FILE = 'Comprehensive Game Export and Analysis.xlsx'

CHANNELS = {
    'Digital Board Gamer': 'https://www.youtube.com/@DigitalBoardGamer',
    'Game-Night with Saisha': 'https://www.youtube.com/@GameNightwithSaisha',
    'Peaky Boardgamer': 'https://www.youtube.com/@PeakyBoardgamer'
}

def clean_title(title):
    # Remove common youtube noise like "Review", "How to play", "Top 10"
    title = re.sub(r'(?i)\b(review|how to play|top \d+|playthrough|unboxing|tutorial|setup)\b', '', title)
    title = re.sub(r'[^\w\s]', '', title) # Remove punctuation
    return title.strip().lower()

def main():
    print("Loading existing spreadsheet data...")
    df = pd.read_excel(SPREADSHEET_FILE)
    
    # Assuming 'Game Title' is the column based on previous browser check
    if 'Game Title' in df.columns:
        existing_games = df['Game Title'].dropna().tolist()
    else:
        # Fallback to second column if header was weird
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
                if count >= 100: # Limit to 100 most recent for now to prevent long execution
                    break
                count += 1
                
                vid_title = video.get('title', {}).get('runs', [{}])[0].get('text', '')
                if not vid_title:
                    continue
                
                vid_title_clean = clean_title(vid_title)
                
                # Check for matches
                best_match = None
                best_score = 0
                for game, game_clean in zip(existing_games, existing_games_clean):
                    if len(game_clean) < 3: # Skip very short names
                        continue
                    
                    # Direct substring match
                    if game_clean in vid_title_clean:
                        best_score = 100
                        best_match = game
                        break
                        
                    # Fuzzy match
                    score = fuzz.partial_ratio(game_clean, vid_title_clean)
                    if score > best_score:
                        best_score = score
                        best_match = game
                
                if best_score < 85: # Threshold for considering it "missing"
                    missing_reports.append({
                        'Channel': channel_name,
                        'Video Title': vid_title,
                        'Best Match Attempt': best_match,
                        'Match Score': best_score
                    })
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
