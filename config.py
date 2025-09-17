import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN not found in .env')

logging.basicConfig(level=logging.INFO)

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
