CHANNELS = {
    'Digital Board Gamer': 'https://www.youtube.com/@DigitalBoardGamer',
    'Game-Night with Saisha': 'https://www.youtube.com/@GameNightwithSaisha',
    'Peaky Boardgamer': 'https://www.youtube.com/@PeakyBoardgamer',
}

DB_NAME = 'orchestrator_state.db'
SPREADSHEET_FILE = 'Comprehensive Game Export and Analysis.xlsx'
OUTPUT_FILE = 'Updated_Comprehensive_Game_Export.xlsx'

GEMINI_MODEL = 'gemini-2.5-flash'
VIDEOS_PER_CHANNEL = 50
RATE_LIMIT_SECONDS = 2

# Explicit list of video IDs to skip (known off-topic content).
# Safer than heuristic keyword filtering which risks skipping legitimate videos.
SKIP_VIDEO_IDS = {
    'TqX3y5qAhLg',  # "Which Dice Tower Host Has the Most Top 100 Games on BGA? Take 2!"
    'vdom0yH7-NQ',  # "Board Game Creators Take on 7 Wonders Dice"
}

# Generic skip keywords applied to ALL channels (clearly non-game content)
SKIP_TITLE_KEYWORDS = [
    'channel update', 'vlog', 'q&a', 'giveaway', 'unboxing haul', 'live stream',
]
