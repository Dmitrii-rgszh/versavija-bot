#!/usr/bin/env python3
"""
Модуль для обработки приветственных сообщений новым участникам группы.
Отправляет случайное дружелюбное приветствие через 30 секунд после присоединения.
"""

import random
import asyncio
import logging
import json
from pathlib import Path
from aiogram.types import Message
from aiogram.filters import Command
from aiogram import F
from config import bot, dp
from db import get_setting, set_setting

# ID целевой группы для приветственных сообщений
TARGET_GROUP_ID = -1002553563891  # Versavija_test_group

DEFAULT_WELCOME_MESSAGES = [
    "🌟 **Добро пожаловать в нашу дружную компанию!** 🌟\nПривет! Я Версавия - фотограф, который поможет сохранить ваши самые яркие моменты! 📸✨ Рада видеть вас здесь!",
    "👋 **Привет-привет, новый друг!** 👋\nКак здорово, что вы к нам присоединились! 🥳 Я Версавия, и я создаю волшебные кадры, которые останутся с вами навсегда! 📷💫",
    "🎉 **Ура! У нас пополнение!** 🎉\nДобро пожаловать! Меня зовут Версавия, и я обожаю фотографировать! 📸 Здесь вы найдете вдохновение и красивые кадры! 🌈",
    "💝 **Тёплый приём для нового участника!** 💝\nПривет! Версавия на связи! 😊 Рада, что наша творческая семья стала больше! Вместе мы создадим незабываемые моменты! 📸✨",
    "🌸 **Добро пожаловать в мир прекрасных снимков!** 🌸\nПривет! Я Версавия - ваш проводник в мире фотографии! 📷 Здесь каждый кадр - это история! Рада знакомству! 😍",
    "🚀 **Новое лицо в нашей галерее!** 🚀\nПриветствую! Версавия здесь! 👋 Спасибо, что выбрали нас! Вместе создадим что-то невероятное! 📸💎",
    "🦋 **Какая приятная встреча!** 🦋\nЗдравствуйте! Версавия рада новому знакомству! 😊 Наша группа - это место, где рождаются самые красивые воспоминания! 📷🌟",
    "🎨 **Творческое пополнение!** 🎨\nПривет! Меня зовут Версавия, и я безумно люблю своё дело! 📸 Добро пожаловать в наш уютный уголок красоты и вдохновения! ✨",
    "🌺 **Сердечно приветствуем!** 🌺\nПривет-привет! Версавия на связи! 👋 Так рада, что вы здесь! Вместе мы создадим множество прекрасных моментов! 📷💕",
    "🎪 **Праздник к нам пришёл!** 🎪\nУра! Новый участник! 🥳 Версавия приветствует вас! Здесь каждый день - это возможность запечатлеть что-то особенное! 📸🌈"
]

def _load_messages_from_json() -> list[str]:
    path = Path(__file__).parent / 'media' / 'welcome_messages.json'
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list) and all(isinstance(x, str) for x in data) and data:
            return data
        logging.warning("welcome_messages.json пустой или некорректный — используем встроенные сообщения")
    except FileNotFoundError:
        logging.warning("welcome_messages.json не найден — используем встроенные сообщения")
    except Exception as e:
        logging.warning("Не удалось загрузить welcome_messages.json: %s — используем встроенные сообщения", e)
    return DEFAULT_WELCOME_MESSAGES

WELCOME_MESSAGES = _load_messages_from_json()

def _choose_welcome_text() -> str:
    msgs = list(WELCOME_MESSAGES)
    if not msgs:
        return random.choice(DEFAULT_WELCOME_MESSAGES)

    # Загружаем последние N сообщений (как сами тексты)
    try:
        raw = get_setting('welcome_recent_texts', '') or ''
        recent = [s for s in raw.split('\n') if s]
    except Exception:
        recent = []

    # Фильтруем, избегая последних до 5
    block = set(recent[-5:]) if recent else set()
    pool = [m for m in msgs if m not in block] or msgs

    choice = random.choice(pool)

    # Обновляем список последних (не более 10 храним для экономии места)
    try:
        updated = (recent + [choice])[-10:]
        set_setting('welcome_recent_texts', '\n'.join(updated))
    except Exception:
        pass
    return choice


async def send_welcome_message(chat_id: int, new_members: list):
    """
    Отправляет приветственное сообщение новым участникам с задержкой 30 секунд.
    
    Args:
        chat_id: ID группы/канала
        new_members: Список новых участников
    """
    try:
        # Ждем 30 секунд перед отправкой приветствия
        await asyncio.sleep(30)
        
        # Отправляем персональное приветствие каждому новому участнику
        for member in new_members:
            # Выбираем случайное сообщение так, чтобы не повторять последние 5
            welcome_text = _choose_welcome_text()
            
            # Формируем обращение к пользователю
            if member.username:
                user_mention = f"@{member.username}"
            else:
                # Если нет username, используем имя с ссылкой на профиль
                user_mention = f"[{member.full_name}](tg://user?id={member.id})"
            
            # Добавляем обращение к пользователю в начало сообщения
            personalized_message = f"{user_mention}, {welcome_text}"
            
            # Отправляем сообщение в группу
            await bot.send_message(
                chat_id=chat_id,
                text=personalized_message,
                parse_mode="Markdown"
            )
            
            # Небольшая задержка между сообщениями, если участников несколько
            if len(new_members) > 1:
                await asyncio.sleep(2)
        
        logging.info(f"Отправлено {len(new_members)} приветственных сообщений в группу {chat_id}")
        
    except Exception as e:
        logging.error(f"Ошибка при отправке приветственного сообщения: {e}")


@dp.message(F.new_chat_members)
async def handle_new_members(message: Message):
    """
    Обрабатывает событие присоединения новых участников к группе.
    Запускает отправку приветственного сообщения с задержкой.
    """
    logging.info(f"📨 СОБЫТИЕ: new_chat_members в чате {message.chat.id} ({message.chat.type})")
    
    # Проверяем, что сообщение из целевой группы и содержит новых участников
    if (message.chat.id == TARGET_GROUP_ID and 
        message.new_chat_members and 
        len(message.new_chat_members) > 0):
        
        new_members = message.new_chat_members
        
        # Фильтруем ботов (не приветствуем ботов)
        human_members = [member for member in new_members if not member.is_bot]
        
        if human_members:
            logging.info(f"Новые участники в группе {message.chat.title}: {[m.full_name for m in human_members]}")
            
            # Запускаем задачу отправки приветствия в фоне
            asyncio.create_task(
                send_welcome_message(message.chat.id, human_members)
            )
        else:
            logging.info("Новые участники - боты, приветствие не отправляется")
    else:
        if message.chat.id != TARGET_GROUP_ID:
            logging.info(f"Событие из другого чата: {message.chat.id} (целевой: {TARGET_GROUP_ID})")


# Отладочный обработчик для диагностики
@dp.message()
async def debug_all_messages(message: Message):
    """Отладочный обработчик - логирует сообщения из целевого чата"""
    if message.chat.id == TARGET_GROUP_ID:
        logging.info(f"📨 ОТЛАДКА: Сообщение в целевом чате {message.chat.id}")
        logging.info(f"   Тип чата: {message.chat.type}")
        logging.info(f"   Название: {message.chat.title}")
        logging.info(f"   Новые участники: {message.new_chat_members}")
        logging.info(f"   Покинувшие: {message.left_chat_member}")
        logging.info(f"   Текст: {message.text and message.text[:50]}")


# Альтернативная команда приветствия для каналов
@dp.message(Command(commands=['welcome']))
async def manual_welcome_command(message: Message):
    """
    Команда для ручного запроса приветствия.
    Работает в любых чатах, включая каналы.
    """
    try:
        # Выбираем сообщение без повтора последних 5
        welcome_text = _choose_welcome_text()

        # Формируем персональное обращение
        user = message.from_user
        if user.username:
            user_mention = f"@{user.username}"
        else:
            user_mention = f"[{user.full_name}](tg://user?id={user.id})"

        personalized_message = f"{user_mention}, {welcome_text}"

        # Отправляем приветствие
        await message.reply(
            text=personalized_message,
            parse_mode="Markdown"
        )

        logging.info(f"Отправлено приветствие по команде пользователю {user.full_name} в чате {message.chat.id}")

    except Exception as e:
        logging.error(f"Ошибка команды /welcome: {e}")
        await message.reply("Произошла ошибка при отправке приветствия 😔")


def setup_welcome_handlers():
    """
    Настройка обработчиков приветственных сообщений.
    Вызывается при инициализации бота.
    """
    logging.info(f"Настроены обработчики приветственных сообщений для группы ID: {TARGET_GROUP_ID}")
    logging.info(f"Загружено {len(WELCOME_MESSAGES)} приветственных сообщений (источник: JSON или встроенный fallback)")
    logging.info("Доступные функции:")
    logging.info("  • Автоматическое приветствие в группах/супергруппах")
    logging.info("  • Команда /welcome для ручного приветствия")
    logging.info("  • Отладочное логирование событий")
    
    # Информируем о типе целевого чата
    if str(TARGET_GROUP_ID).startswith("-100"):
        logging.info("  ⚠️ ID указывает на супергруппу/канал - убедитесь что это именно ГРУППА!")
    logging.info(f"  📊 Для отладки проверяйте логи с префиксом '📨 ОТЛАДКА'")
    
    return True


if __name__ == "__main__":
    # Для тестирования модуля
    print("Модуль приветственных сообщений загружен")
    print(f"Целевая группа: {TARGET_GROUP_ID}")
    print(f"Количество приветственных сообщений: {len(WELCOME_MESSAGES)}")
    
    # Показываем одно из сообщений для примера
    print(f"\nПример приветственного сообщения:")
    print(random.choice(WELCOME_MESSAGES))