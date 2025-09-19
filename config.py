import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
import sys

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN not found in .env')

# Client API credentials
API_ID = int(os.getenv('API_ID', '21700254'))
API_HASH = os.getenv('API_HASH', '5d82759692cfedc1170598a5d5cd2ad9')

logging.basicConfig(level=logging.INFO)

# Force UTF-8 output to avoid mojibake on Windows terminals
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Admin IDs (integers) loaded from .env variable ADMIN_IDS="123,456"; fallback empty set
ADMIN_IDS: set[int] = set()
_env_ids = os.getenv('ADMIN_IDS', '')
for part in _env_ids.split(','):
    part = part.strip()
    if part.isdigit():
        ADMIN_IDS.add(int(part))

# Shared bot and dispatcher
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# Mapping defaults (Yandex Maps deep-linking)
# Samara city center by default: (lat, lon)
DEFAULT_CITY_NAME = os.getenv('DEFAULT_CITY_NAME', 'Самара')
# Note: store as (lat, lon) tuple; Yandex ll param expects lon,lat order
DEFAULT_CITY_CENTER = (
    float(os.getenv('DEFAULT_CITY_LAT', '53.195878')),
    float(os.getenv('DEFAULT_CITY_LON', '50.100202')),
)
MAP_ZOOM_DEFAULT = int(os.getenv('MAP_ZOOM_DEFAULT', '16'))
