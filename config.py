"""Loads scanner_config.yaml and exposes all domain-specific constants.

Every other module imports from here — nothing else reads the YAML directly.
Override the config path via the SCANNER_CONFIG environment variable.
"""

import os
import sys

import yaml

_CONFIG_PATH = os.environ.get(
    'SCANNER_CONFIG',
    os.path.join(os.path.dirname(__file__), 'scanner_config.yaml'),
)

try:
    with open(_CONFIG_PATH) as f:
        _cfg = yaml.safe_load(f)
except FileNotFoundError:
    print(f"FATAL: config file not found: {_CONFIG_PATH}", file=sys.stderr)
    sys.exit(1)

# -- Channels ---------------------------------------------------------------
CHANNELS = _cfg['channels']

# -- LLM / Gemini -----------------------------------------------------------
GEMINI_MODEL = _cfg['llm']['model']
RATE_LIMIT_SECONDS = _cfg['llm']['rate_limit_seconds']

# -- Orchestrator ------------------------------------------------------------
_orch = _cfg['orchestrator']
DB_NAME = _orch['db_name']
VIDEOS_PER_CHANNEL = _orch['videos_per_channel']
LOG_FILE = _orch['log_file']
OUTPUT_JSONL = _orch['output_jsonl']
SKIP_VIDEO_IDS = set(_orch.get('skip_video_ids', []))
SKIP_TITLE_KEYWORDS = _orch.get('skip_title_keywords', [])
EXTRACTION_PROMPT = _orch['extraction_prompt']

# -- Extraction (extract_all.py) ---------------------------------------------
_ext = _cfg['extraction']
SPREADSHEET_FILE = _ext['spreadsheet_file']
OUTPUT_FILE = _ext['output_file']
FUZZY_MATCH_THRESHOLD = _ext['fuzzy_match_threshold']
MIN_TITLE_LENGTH = _ext['min_title_length']
TITLE_CLEANING_PATTERNS = _ext['title_cleaning_patterns']
TITLE_SPLIT_SEPARATORS = _ext['title_split_separators']
EXCLUDED_SHORT_WORDS = _ext['excluded_short_words']
BGA_DETECTION_KEYWORDS = _ext['bga_detection_keywords']
NEW_ENTRY_COLUMNS = _ext['new_entry_columns']

# -- Validation (validate_data.py) -------------------------------------------
_val = _cfg['validation']
VALIDATION_FUZZY_THRESHOLD = _val['fuzzy_threshold']
VALIDATION_VIDEO_LIMIT = _val['video_limit']
VALIDATION_OUTPUT_REPORT = _val['output_report']
VALIDATION_TITLE_PATTERN = _val['title_cleaning_pattern']

# -- Testing (test_gemini.py) ------------------------------------------------
_test = _cfg['testing']
TEST_VIDEO_URL = _test['video_url']
TEST_PROMPT = _test['prompt']
