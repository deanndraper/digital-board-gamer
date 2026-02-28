import pandas as pd
import scrapetube
from fuzzywuzzy import fuzz
import re

SPREADSHEET_FILE = 'Comprehensive Game Export and Analysis.xlsx'
OUTPUT_FILE = 'Updated_Comprehensive_Game_Export.xlsx'

CHANNELS = {
    'Digital Board Gamer': 'https://www.youtube.com/@DigitalBoardGamer',
    'Game-Night with Saisha': 'https://www.youtube.com/@GameNightwithSaisha',
    'Peaky Boardgamer': 'https://www.youtube.com/@PeakyBoardgamer'
}

def smart_clean_title(title):
    # Common prefixes / suffixes to drop entirely
    to_drop = [
        r"(?i)how to play",
        r"(?i)review",
        r"(?i)top \d+",
        r"(?i)playthrough",
        r"(?i)unboxing",
        r"(?i)tutorial",
        r"(?i)setup",
        r"(?i)board game arena",
        r"(?i)bga",
        r"(?i)full teach",
        r"(?i)visuals",
        r"(?i)1 minute overview",
        r"(?i)overview",
        r"(?i)on board game arena",
        r"(?i)relaxing solo playthrough",
        r"(?i)perfect for winding down",
        r"(?i)in \d+ mins?",
        r"(?i)in \d+ minutes?",
        r"(?i)game overview"
    ]
    
    clean = title
    for p in to_drop:
        clean = re.sub(p, '', clean)
        
    # Split on common separators that usually divide the game name from commentary
    splits = re.split(r'[-–|:!+,]|\b(Re-upload|Preview|Update)\b', clean)
    
    # Try to find the most "name-like" part (usually the first non-empty string or the longest)
    # Actually, the game name is usually the very first part before a dash or colon.
    best_part = ""
    for part in splits:
        if part and part.strip():
            best_part = part.strip()
            break
            
    # Clean up random symbols
    best_part = re.sub(r'[^\w\s\']', '', best_part).strip()
    return best_part

def main():
    print("Loading existing spreadsheet data...")
    try:
        df = pd.read_excel(SPREADSHEET_FILE)
    except FileNotFoundError:
        print(f"Could not find {SPREADSHEET_FILE}")
        return

    # Find Game Title column
    title_col = None
    if 'Game Title' in df.columns:
        title_col = 'Game Title'
    else:
        title_col = df.columns[1] # fallback
        
    existing_games = df[title_col].dropna().tolist()
    
    # We maintain a lowercased, stripped version for matching
    existing_games_lower = [g.lower().strip() for g in existing_games]

    print(f"Loaded {len(existing_games)} existing games.")

    new_games_to_add = []
    seen_new_candidates = set() # To prevent adding duplicates internally

    for channel_name, url in CHANNELS.items():
        print(f"\nFetching all videos for {channel_name}...")
        try:
            # We fetch all instead of limit
            videos = scrapetube.get_channel(channel_url=url)
            count = 0
            for video in videos:
                count += 1
                if count % 50 == 0:
                    print(f" Processed {count} videos...")
                    
                vid_title = video.get('title', {}).get('runs', [{}])[0].get('text', '')
                if not vid_title:
                    continue
                
                extracted_name = smart_clean_title(vid_title)
                
                # Filter out garbage short names or purely numeric or "Top"
                if len(extracted_name) < 3 or extracted_name.isnumeric():
                    continue
                if extracted_name.lower() in ['top', 'the', 'and', 'with']:
                    continue
                    
                extracted_lower = extracted_name.lower()
                
                # Check against existing games (fuzzy match)
                best_score_existing = 0
                for eg in existing_games_lower:
                    if len(eg) < 3:
                        continue
                    if eg in extracted_lower or extracted_lower in eg:
                        best_score_existing = 100
                        break
                    score = fuzz.ratio(eg, extracted_lower)
                    if score > best_score_existing:
                        best_score_existing = score
                        
                if best_score_existing >= 85:
                    continue # Already in spreadsheet

                # Check against candidates already in the loop to prevent duplicates
                is_duplicate = False
                for seen in seen_new_candidates:
                    if fuzz.ratio(seen.lower(), extracted_lower) >= 85 or extracted_lower in seen.lower() or seen.lower() in extracted_lower:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    seen_new_candidates.add(extracted_name)
                    # Create new row entry
                    new_games_to_add.append({
                        title_col: extracted_name,
                        'Score': 'TBD',
                        'Top 10 Rank': '',
                        'Top 10 Year': '',
                        'BGA Review': 'TRUE' if 'BGA' in vid_title or 'Board Game Arena' in vid_title else '',
                        'Pick of the Week': '',
                        'Honorable Mention': '',
                        # Optionally we could add a column "Source Channel" but we stick to the existing schema
                    })
                    
        except Exception as e:
            print(f"Error fetching {channel_name}: {e}")

    print(f"\nFound {len(new_games_to_add)} new unique games to add!")
    
    if new_games_to_add:
        new_df = pd.DataFrame(new_games_to_add)
        combined_df = pd.concat([df, new_df], ignore_index=True)
        
        # Write back to new file
        combined_df.to_excel(OUTPUT_FILE, index=False)
        print(f"Successfully saved updated list to {OUTPUT_FILE}")
    else:
        print("No new games added.")

if __name__ == "__main__":
    main()
