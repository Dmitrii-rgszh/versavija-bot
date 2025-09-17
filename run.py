import asyncio
import logging
from config import bot, dp
# В контейнере запускается run.py напрямую, поэтому надо явно импортировать handlers,
# чтобы декораторы зарегистрировали обработчики (/start и т.д.).
import handlers  # noqa: F401  (side-effect import)
import welcome_messages  # импорт модуля приветственных сообщений
from aiogram.types import BotCommand
from db import init_db  # ensure DB (including new bookings table) is initialized before polling


async def _set_bot_commands():
    try:
        cmds = [
            BotCommand(command='start', description='Начать / Главное меню'),
            BotCommand(command='adminmode', description='Переключить режим администратора'),
            BotCommand(command='help', description='Справка'),
        ]
        await bot.set_my_commands(cmds)
        logging.info('Bot commands set: %s', ', '.join(c.command for c in cmds))
    except Exception:
        logging.exception('Failed to set bot commands')


async def main():
    try:
        # Initialize / migrate database (adds new tables if they don't exist)
        try:
            init_db()
            logging.info('Database initialized (tables ensured)')
        except Exception:
            logging.exception('Failed to initialize database')

        # Настройка приветственных сообщений
        welcome_messages.setup_welcome_handlers()

        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logging.info('Webhook deleted before polling start')
        except Exception:
            logging.exception('Failed to delete webhook before polling start')

        await _set_bot_commands()

        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
