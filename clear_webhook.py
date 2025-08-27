import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

if not TOKEN:
    print('BOT_TOKEN not found in .env')
    raise SystemExit(1)

from aiogram import Bot

async def main():
    bot = Bot(TOKEN)
    try:
        ok = await bot.delete_webhook(drop_pending_updates=True)
        print('delete_webhook ->', ok)
    except Exception as e:
        print('Error deleting webhook:', e)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
