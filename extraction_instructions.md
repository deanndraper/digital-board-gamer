# Game Extraction Instructions

You are analyzing a board game YouTube video transcript. Extract structured data about every board game mentioned.

## For each game, extract:
- **title**: The name of the game
- **ranking**: The numerical ranking given in this video (e.g., 1 if it is their #1 game). Use null if no rank is given.
- **ranking_source**: Categorize where the ranking comes from:
  - "personal" — the reviewer's own personal top-X or ranked list
  - "bga_popularity_yearly" — Board Game Arena most-played or hottest games for a specific year
  - "bga_popularity_alltime" — Board Game Arena most-played games of all time
  - "community_poll" — community vote, poll, or award results
  - null — if no ranking is given
- **score**: The reviewer's personal numeric rating (e.g., 7/10, 8.5/10). Use null if no personal rating is given. Do NOT put vote percentages, poll results, or community vote shares here — only the reviewer's own score out of 10.
- **vote_percentage**: If the video is about awards or polls, the percentage of votes this game received. Use null otherwise.
- **award_category**: If the game won or was nominated in an award category, the category name. Use null otherwise.
- **opinion**: A brief summary of the reviewer's subjective opinion of this specific game.

## Also extract:
- **summary**: A brief summary of the overall video
- **classification**: Choose one of: "best of year", "how to play", "new game including how to play", "new game including how to play and rating", "review", "playthrough", "other"

## Output format
Return ONLY a JSON object matching this schema:
```json
{
    "games": [
        {
            "title": "Game Name",
            "ranking": 1,
            "ranking_source": "personal",
            "score": 9.5,
            "vote_percentage": null,
            "award_category": null,
            "opinion": "Brief opinion text"
        }
    ],
    "summary": "...",
    "classification": "..."
}
```

Do not include markdown fences, commentary, or any text outside the JSON object.
