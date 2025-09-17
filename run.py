import asyncio
import logging
from config import bot, dp
# В контейнере запускается run.py напрямую, поэтому надо явно импортировать handlers,
# чтобы декораторы зарегистрировали обработчики (/start и т.д.).
import handlers  # noqa: F401  (side-effect import)
import welcome_messages  # импорт модуля приветственных сообщений
from birthday_scheduler import setup_birthday_scheduler
from aiogram.types import BotCommand
from db import init_db  # ensure DB (including new bookings table) is initialized before polling


async def _set_bot_commands():
    try:
        cmds = [
            BotCommand(command='start', description='Начать / Главное меню'),
            BotCommand(command='help', description='Справка'),
        ]
        await bot.set_my_commands(cmds)
        logging.info('Bot commands set: %s', ', '.join(c.command for c in cmds))
    except Exception:
        logging.exception('Failed to set bot commands')


async def main():
    try:
        # Reduce noise from third-party libraries while keeping our INFO logs
        try:
            logging.getLogger('telethon').setLevel(logging.WARNING)
            logging.getLogger('aiohttp').setLevel(logging.WARNING)
        except Exception:
            pass
        # Initialize / migrate database (adds new tables if they don't exist)
        try:
            init_db()
            logging.info('Database initialized (tables ensured)')
        except Exception:
            logging.exception('Failed to initialize database')

        # Настройка стандартной системы приветствий (для групп/супергрупп)
        welcome_messages.setup_welcome_handlers()
        # Планировщик поздравлений с ДР и DM-промо
        try:
            await setup_birthday_scheduler()
        except Exception as e:
            logging.warning('Не удалось запустить планировщик ДР: %s', e)
        
        # Настройка системы отслеживания подписчиков канала через Client API
        try:
            from simple_tracker import setup_simple_tracking
            await setup_simple_tracking()
            logging.info('Simple tracking system initialized with full automation')
        except Exception as e:
            # Если упрощенный трекер не работает, используем автоматический мониторинг
            try:
                from auto_monitor import setup_auto_monitoring
                await setup_auto_monitoring()
                logging.info('Automatic monitoring system initialized as fallback')
            except Exception as e2:
                # Если и автоматический мониторинг не работает, используем демо версию
                try:
                    from demo_tracker import setup_demo_tracking
                    await setup_demo_tracking()
                    logging.info('Demo tracking system initialized as final fallback')
                except Exception as e3:
                    logging.info(f'No tracking system available: {e3}')

        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logging.info('Webhook deleted before polling start')
        except Exception:
            logging.exception('Failed to delete webhook before polling start')

        await _set_bot_commands()

        # Запускаем Bot API polling
        logging.info("🤖 Запускаем Bot API polling...")
        await dp.start_polling(bot)
        
        # await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
