# Prefilter Instructions

You are deciding whether a YouTube video is worth extracting board game data from.

Given a video title and description, determine if this video is a board game review, ranking, top-10 list, or top-X list where the reviewer discusses specific board games with opinions or ratings.

## Answer YES if:
- The title contains words like "review", "ranking", "top 10", "top 5", "best games", "worst games", or similar rating/opinion language
- The video appears to be a list or ranking of board games
- The video is a dedicated review of one or more specific board games

## Answer NO if:
- The video is clearly a playthrough, let's play, or actual gameplay session
- The video is a preview, unboxing, or news update with no opinions/ratings
- The video is unrelated to board games
- The video is a tutorial/how-to-play with no review or rating component

## Output format
Respond with ONLY "YES" or "NO" followed by a brief reason on the same line.

Example: "YES — title says 'Top 10 Games of 2025' which is a ranking list"
Example: "NO — title says 'Full Playthrough' which is gameplay, not a review"
