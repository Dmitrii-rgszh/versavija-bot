#!/usr/bin/env python3
"""
Скрипт для получения информации о чате/группе.
Запустите этот скрипт и отправьте любое сообщение в группу где добавлен бот.
"""

import asyncio
import logging
from config import bot, dp
from aiogram.types import Message

logging.basicConfig(level=logging.INFO)

@dp.message()
async def get_chat_info(message: Message):
    chat = message.chat
    print(f"\n{'='*50}")
    print(f"📋 ИНФОРМАЦИЯ О ЧАТЕ:")
    print(f"{'='*50}")
    print(f"ID чата: {chat.id}")
    print(f"Название: {chat.title}")
    print(f"Тип: {chat.type}")
    print(f"Описание: {chat.description}")
    print(f"Username: @{chat.username}" if chat.username else "Username: отсутствует")
    print(f"{'='*50}\n")

async def main():
    print("Бот запущен. Отправьте любое сообщение в группу где добавлен бот...")
    print("Информация о группе будет выведена в консоль.")
    print("Нажмите Ctrl+C для остановки.")
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\nОстановлено пользователем")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())