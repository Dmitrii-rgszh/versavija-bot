#!/usr/bin/env python3
"""
Версия бота для локального тестирования с webhook вместо polling
Избегает конфликтов с основным ботом на сервере
"""

import asyncio
import logging
from aiohttp import web
from aiohttp.web_request import Request
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.types import Update
import os
from dotenv import load_dotenv
import handlers  # импорт основных обработчиков
import welcome_messages  # импорт приветственных сообщений
from db import init_db

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_HOST = 'localhost'
WEBHOOK_PORT = 8080
WEBHOOK_PATH = f'/webhook/{BOT_TOKEN}'
WEBHOOK_URL = f'http://{WEBHOOK_HOST}:{WEBHOOK_PORT}{WEBHOOK_PATH}'

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def webhook_handler(request: Request, bot: Bot) -> web.Response:
    """Обработчик webhook запросов"""
    try:
        # Получение обновления из запроса
        update_data = await request.json()
        update = Update.model_validate(update_data, from_attributes=True)
        
        # Обработка обновления
        await dp.feed_update(bot, update)
        
        return web.Response()
    except Exception as e:
        logging.error(f"Ошибка в webhook handler: {e}")
        return web.Response(status=500)

async def main():
    """Основная функция запуска"""
    try:
        # Инициализация БД
        init_db()
        logging.info('Database initialized')
        
        # Настройка приветственных сообщений
        welcome_messages.setup_welcome_handlers()
        
        # Установка webhook
        await bot.set_webhook(url=WEBHOOK_URL)
        logging.info(f'Webhook set to: {WEBHOOK_URL}')
        
        # Создание веб-приложения
        app = web.Application()
        
        # Регистрация обработчика webhook
        app.router.add_post(WEBHOOK_PATH, 
                           lambda req: webhook_handler(req, bot))
        
        # Добавление информационного эндпоинта
        async def info_handler(request):
            return web.Response(text=f"Versavija Bot Webhook Server\nListening on: {WEBHOOK_URL}")
        
        app.router.add_get('/', info_handler)
        
        # Запуск сервера
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, WEBHOOK_HOST, WEBHOOK_PORT)
        await site.start()
        
        logging.info(f'Webhook server started on http://{WEBHOOK_HOST}:{WEBHOOK_PORT}')
        logging.info('Bot is running with webhook...')
        
        # Бесконечный цикл для поддержания сервера
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logging.info('Stopping bot...')
        finally:
            # Очистка ресурсов
            await bot.delete_webhook()
            await runner.cleanup()
            await bot.session.close()
            
    except Exception as e:
        logging.error(f"Error in main: {e}")
        await bot.session.close()

if __name__ == '__main__':
    print("🚀 Запуск локального бота с webhook...")
    print(f"📡 Webhook URL: http://{WEBHOOK_HOST}:{WEBHOOK_PORT}{WEBHOOK_PATH}")
    print("⚠️  Для тестирования используйте ngrok или локальное подключение")
    print("🔧 Нажмите Ctrl+C для остановки")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")