#!/usr/bin/env python3
"""
Скрипт для получения информации о группе без polling.
Просто получите chat_id из любого сообщения в группе и вставьте его сюда.
"""

import asyncio
from config import bot

async def get_chat_info(chat_id):
    """Получить информацию о чате по его ID"""
    try:
        chat = await bot.get_chat(chat_id)
        print(f"\n{'='*50}")
        print(f"📋 ИНФОРМАЦИЯ О ЧАТЕ:")
        print(f"{'='*50}")
        print(f"ID чата: {chat.id}")
        print(f"Название: {chat.title}")
        print(f"Тип: {chat.type}")
        print(f"Описание: {chat.description}")
        print(f"Username: @{chat.username}" if chat.username else "Username: отсутствует")
        print(f"Количество участников: {await bot.get_chat_member_count(chat_id)}")
        print(f"{'='*50}\n")
        
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        await bot.session.close()

async def main():
    print("Введите chat_id группы (можно получить из @userinfobot или других источников):")
    print("Или нажмите Enter для использования тестового ID")
    
    chat_id_input = input("Chat ID: ").strip()
    
    if not chat_id_input:
        print("Используется тестовый режим...")
        return
    
    try:
        chat_id = int(chat_id_input)
        await get_chat_info(chat_id)
    except ValueError:
        print("Неверный формат chat_id. Введите число.")

if __name__ == "__main__":
    asyncio.run(main())