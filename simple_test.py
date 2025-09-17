#!/usr/bin/env python3
"""
Простой тест отправки сообщения в группу без polling
"""

import asyncio
import random
import os
from aiogram import Bot

# Вставьте ваш токен бота сюда
BOT_TOKEN = os.getenv('BOT_TOKEN', '7815199281:AAHIW7FWqgUDAOrBqZFMwVnqoiaq-P7gbQQ')
TARGET_GROUP_ID = -1002553563891

WELCOME_MESSAGES = [
    "🌟 **Добро пожаловать в нашу дружную компанию!** 🌟\nПривет! Я Версавия - фотограф, который поможет сохранить ваши самые яркие моменты! 📸✨ Рада видеть вас здесь!",
    
    "👋 **Привет-привет, новый друг!** 👋\nКак здорово, что вы к нам присоединились! 🥳 Я Версавия, и я создаю волшебные кадры, которые останутся с вами навсегда! 📷💫",
    
    "🎉 **Ура! У нас пополнение!** 🎉\nДобро пожаловать! Меня зовут Версавия, и я обожаю фотографировать! 📸 Здесь вы найдете вдохновение и красивые кадры! 🌈"
]

async def test_send_message():
    bot = Bot(token=BOT_TOKEN)
    
    try:
        welcome_text = random.choice(WELCOME_MESSAGES)
        test_message = f"🧪 **ТЕСТ ПРИВЕТСТВИЯ:**\n\n{welcome_text}\n\n_(Это тест функционала для новых участников)_"
        
        result = await bot.send_message(
            chat_id=TARGET_GROUP_ID,
            text=test_message,
            parse_mode="Markdown"
        )
        
        print(f"✅ Тестовое сообщение отправлено!")
        print(f"📝 ID сообщения: {result.message_id}")
        print(f"🎯 Группа: {TARGET_GROUP_ID}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    print("🚀 Отправка тестового приветственного сообщения...")
    asyncio.run(test_send_message())