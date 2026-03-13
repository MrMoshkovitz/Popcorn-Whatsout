import os

# Load .env file manually
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.isfile(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'popcorn.db')

# TMDB
TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_LANGUAGE_PRIMARY = "he-IL"
TMDB_LANGUAGE_FALLBACK = "en-US"
WATCH_REGION = "IL"
API_DELAY_SECONDS = 0.2

# Matching
MATCH_CONFIDENCE_THRESHOLD = 0.6

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_ADMIN_CHAT_ID = os.getenv('TELEGRAM_ADMIN_CHAT_ID', '')

# Disambiguation
DISAMBIGUATION_TIMEOUT_HOURS = 48

# Logging
import logging

LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
