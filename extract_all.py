import pandas as pd
import scrapetube
from fuzzywuzzy import fuzz
import re

from config import (
    CHANNELS, SPREADSHEET_FILE, OUTPUT_FILE,
    TITLE_CLEANING_PATTERNS, TITLE_SPLIT_SEPARATORS,
    FUZZY_MATCH_THRESHOLD, MIN_TITLE_LENGTH, EXCLUDED_SHORT_WORDS,
    BGA_DETECTION_KEYWORDS, NEW_ENTRY_COLUMNS,
)


def smart_clean_title(title):
    clean = title
    for p in TITLE_CLEANING_PATTERNS:
        clean = re.sub(p, '', clean)

    # Split on common separators that usually divide the game name from commentary
    splits = re.split(TITLE_SPLIT_SEPARATORS, clean)

    best_part = ""
    for part in splits:
        if part and part.strip():
            best_part = part.strip()
            break

    best_part = re.sub(r'[^\w\s\']', '', best_part).strip()
    return best_part


def main():
    print("Loading existing spreadsheet data...")
    try:
        df = pd.read_excel(SPREADSHEET_FILE)
    except FileNotFoundError:
        print(f"Could not find {SPREADSHEET_FILE}")
        return

    title_col = 'Game Title' if 'Game Title' in df.columns else df.columns[1]
    existing_games = df[title_col].dropna().tolist()
    existing_games_lower = [g.lower().strip() for g in existing_games]

    print(f"Loaded {len(existing_games)} existing games.")

    new_games_to_add = []
    seen_new_candidates = set()

    for channel_name, url in CHANNELS.items():
        print(f"\nFetching all videos for {channel_name}...")
        try:
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

                if len(extracted_name) < MIN_TITLE_LENGTH or extracted_name.isnumeric():
                    continue
                if extracted_name.lower() in EXCLUDED_SHORT_WORDS:
                    continue

                extracted_lower = extracted_name.lower()

                best_score_existing = 0
                for eg in existing_games_lower:
                    if len(eg) < MIN_TITLE_LENGTH:
                        continue
                    if eg in extracted_lower or extracted_lower in eg:
                        best_score_existing = 100
                        break
                    score = fuzz.ratio(eg, extracted_lower)
                    if score > best_score_existing:
                        best_score_existing = score

                if best_score_existing >= FUZZY_MATCH_THRESHOLD:
                    continue

                is_duplicate = False
                for seen in seen_new_candidates:
                    if fuzz.ratio(seen.lower(), extracted_lower) >= FUZZY_MATCH_THRESHOLD or extracted_lower in seen.lower() or seen.lower() in extracted_lower:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    seen_new_candidates.add(extracted_name)
                    entry = {title_col: extracted_name}
                    entry['Score'] = NEW_ENTRY_COLUMNS.get('score', '')
                    entry['Top 10 Rank'] = NEW_ENTRY_COLUMNS.get('top_10_rank', '')
                    entry['Top 10 Year'] = NEW_ENTRY_COLUMNS.get('top_10_year', '')
                    entry['BGA Review'] = 'TRUE' if any(kw in vid_title for kw in BGA_DETECTION_KEYWORDS) else ''
                    entry['Pick of the Week'] = NEW_ENTRY_COLUMNS.get('pick_of_the_week', '')
                    entry['Honorable Mention'] = NEW_ENTRY_COLUMNS.get('honorable_mention', '')
                    new_games_to_add.append(entry)

        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"Error fetching {channel_name}: {e}")

    print(f"\nFound {len(new_games_to_add)} new unique games to add!")

    if new_games_to_add:
        new_df = pd.DataFrame(new_games_to_add)
        combined_df = pd.concat([df, new_df], ignore_index=True)
        combined_df.to_excel(OUTPUT_FILE, index=False)
        print(f"Successfully saved updated list to {OUTPUT_FILE}")
    else:
        print("No new games added.")


if __name__ == "__main__":
    main()
