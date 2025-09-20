#!/usr/bin/env python3
# -*- codi    "       "🔥 Новое лицо в нашей галерее!\n\nПриветствую, {name}! Versavija здесь! 👋\n\nСпасибо, что выбрали нас!\n\nВместе создадим что-то невероятное! 📸💎",   "🚀 Новое лицо в нашей галерее!\n\nПриветствую, {name}! Versavija здесь! 👋\n\nСпасибо, что выбрали нас!\n\nВместе создадим что-то невероятное! 📸💎","🌸 Добро пожаловать в мир прекрасных снимков!\n\nПривет, {name}! Я Versavija - ваш проводник в мире фотографии! 📷\n\nЗдесь каждый кадр - это история!\n\nРада знакомству! 😍", Привет-привет, новый друг {name}!\n\nКак здорово, что вы к нам присоединились! 🥳\n\nЯ Versavija, и я создаю волшебные кадры, которые останутся с вами навсегда! 📷💫",g: utf-8 -*-

"""
Упрощенная версия отслеживания подписчиков с полной автоматизацией
"""

import asyncio
import logging
import random
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, Set
from aiogram.types import Message
from aiogram.filters import Command
from config import dp, bot

# Конфигурация
TARGET_CHANNEL_ID = -1002553563891
CHANNEL_USERNAME = "versavija_test_group"  # Используем username для Client API
WELCOME_DELAY = 30  # 30 секунд до приветствия

# Для Pyrogram Client нужны API credentials
API_ID = "21700254"
API_HASH = "5d82759692cfedc1170598a5d5cd2ad9"
PHONE_NUMBER = "+79170386777"
PASSWORD_2FA = "Miron975864...!!!"
SESSION_NAME = "subscriber_tracker"

# Приветственные сообщения от Versavija
WELCOME_MESSAGES = [
    "🌟 Добро пожаловать в нашу дружную компанию, {name}!\n\nПривет! Я Versavija - фотограф, который поможет сохранить ваши самые яркие моменты! 📸✨\n\nРада видеть вас здесь!",
    
    "� Привет-привет, новый друг!\n\nКак здорово, что вы к нам присоединились! 🥳\n\nЯ Versavija, и я создаю волшебные кадры, которые останутся с вами навсегда! 📷💫",
    
    "🎉 Ура! У нас пополнение!\n\nДобро пожаловать, {name}! Меня зовут Versavija, и я обожаю фотографировать! 📸\n\nЗдесь вы найдете вдохновение и красивые кадры! 🌈",
    
    "💝 Тёплый приём для нового участника!\n\nПривет, {name}! Versavija на связи! 😊\n\nРада, что наша творческая семья стала больше!\n\nВместе мы создадим незабываемые моменты! 📸✨",
    
    "� Добро пожаловать в мир прекрасных снимков!\n\nПривет! Я Versavija - ваш проводник в мире фотографии! 📷\n\nЗдесь каждый кадр - это история!\n\nРада знакомству! 😍",
    
    "� Новое лицо в нашей галерее!\n\nПриветствую! Versavija здесь! 👋\n\nСпасибо, что выбрали нас!\n\nВместе создадим что-то невероятное! 📸💎",
    
    "🦋 Какая приятная встреча!\n\nЗдравствуйте, {name}! Versavija рада новому знакомству! 😊\n\nНаша группа - это место, где рождаются самые красивые воспоминания! 📷🌟",
    
    "🎨 Творческое пополнение!\n\nПривет, {name}! Меня зовут Versavija, и я безумно люблю своё дело! 📸\n\nДобро пожаловать в наш уютный уголок красоты и вдохновения! ✨",
    
    "🌺 Сердечно приветствуем!\n\nПривет-привет, {name}! Versavija на связи! 👋\n\nТак рада, что вы здесь!\n\nВместе мы создадим множество прекрасных моментов! 📷💕",
    
    "🎪 Праздник к нам пришёл!\n\nУра! Новый участник {name}! 🥳\n\nVersavija приветствует вас!\n\nЗдесь каждый день - это возможность запечатлеть что-то особенное! 📸🌈"
]

# Глобальные переменные
known_subscribers: Set[int] = set()
pending_welcomes: Dict[int, dict] = {}
client = None
_tl_client = None
DEBUG_BIRTHDAY_LOGS = False

async def _telethon_fetch_birthdate(user_id: int, username: str | None) -> str | None:
    """Пробуем получить дату рождения через Telethon (если Pyrogram не вернул)."""
    global _tl_client
    try:
        from telethon import TelegramClient, functions
    except Exception:
        logging.info("[TL] Telethon не установлен или недоступен")
        return None

    try:
        if _tl_client is None:
            tl_session = f"{SESSION_NAME}_tl"
            _tl_client = TelegramClient(tl_session, int(API_ID), API_HASH)
            await _tl_client.connect()
        if not await _tl_client.is_user_authorized():
            logging.info("[TL] Сессия не авторизована. Выполните: python telethon_login.py")
            return None

        # Получаем entity пользователя
        entity = None
        try:
            if username:
                entity = await _tl_client.get_entity(username)
        except Exception:
            entity = None
        if entity is None:
            try:
                entity = await _tl_client.get_entity(user_id)
            except Exception:
                entity = None
        if entity is None:
            logging.info("[TL] Не удалось получить entity пользователя")
            return None

        full = await _tl_client(functions.users.GetFullUserRequest(id=entity))
        full_user = getattr(full, 'full_user', None) or getattr(full, 'user_full', None) or full
        bd = None
        for attr in ('birthday', 'birthdate', 'birth_date'):
            if hasattr(full_user, attr):
                bd = getattr(full_user, attr)
                break
        if bd is None:
            logging.info("[TL] Атрибут даты рождения отсутствует в объекте")
            return None
        try:
            day = getattr(bd, 'day', None)
            month = getattr(bd, 'month', None)
            year = getattr(bd, 'year', None)
            if isinstance(bd, dict):
                day = day or bd.get('day')
                month = month or bd.get('month')
                year = year or bd.get('year')
            if day and month:
                s = f"{int(month):02d}-{int(day):02d}"
                if year:
                    s = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
                logging.info("[TL] Дата рождения получена: %s", s)
                return s
        except Exception:
            return None
        return None
    except Exception as e:
        logging.info("[TL] Ошибка Telethon: %s", e)
        return None

def create_subscribers_table():
    """Создает/мигрирует таблицу подписчиков в БД"""
    try:
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()

        # Базовое создание, если таблицы нет
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                join_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Миграции: добавляем недостающие колонки (last_name, birthdate)
        try:
            cursor.execute("PRAGMA table_info(subscribers)")
            cols = {row[1] for row in cursor.fetchall()}
            if 'last_name' not in cols:
                cursor.execute('ALTER TABLE subscribers ADD COLUMN last_name TEXT')
            if 'birthdate' not in cols:
                cursor.execute('ALTER TABLE subscribers ADD COLUMN birthdate TEXT')
        except Exception as me:
            # Логируем, но не валим инициализацию
            logging.warning(f"Не удалось выполнить миграцию таблицы subscribers: {me}")

        conn.commit()
        conn.close()
        logging.info("✅ Таблица подписчиков создана/обновлена")

    except Exception as e:
        logging.error(f"❌ Ошибка создания таблицы: {e}")

async def get_channel_subscribers_simple():
    """Простое получение подписчиков с автоматической авторизацией"""
    global client
    
    try:
        from pyrogram import Client
        
        if not client:
            # Создаем клиента с полными данными
            client = Client(
                SESSION_NAME,
                api_id=API_ID,
                api_hash=API_HASH,
                phone_number=PHONE_NUMBER,
                password=PASSWORD_2FA
            )
            
            # Проверяем сессию
            session_file = f"{SESSION_NAME}.session"
            if os.path.exists(session_file):
                logging.info("🔑 Используется сохраненная сессия")
            else:
                logging.info("🔐 Первая авторизация - может потребоваться код из SMS")
                
            await client.start()
            logging.info("✅ Client API готов к работе")
        
        subscribers = []
        
        # Получаем всех участников канала - используем username
        channel_identifier = CHANNEL_USERNAME
        logging.info(f"🔍 Получаем участников канала: @{channel_identifier}")
        
        async for member in client.get_chat_members(channel_identifier):
            user = member.user
            if not user.is_bot:  # Пропускаем ботов
                # Пытаемся получить дату рождения (если есть в полном профиле)
                birthdate_str = None

                # Попробуем получить полный профиль пользователя через RAW API (если поле публично)
                try:
                    from pyrogram.raw.functions.users import GetFullUser
                    peer = await client.resolve_peer(user.id)
                    full = await client.invoke(GetFullUser(id=peer))
                    full_user = getattr(full, 'full_user', None) or getattr(full, 'user_full', None) or full

                    # Ищем атрибут с датой рождения
                    bd = None
                    for attr in ('birthday', 'birthdate', 'birth_date'):
                        bd = getattr(full_user, attr, None)
                        if bd is not None:
                            break
                    if bd is not None:
                        try:
                            day = getattr(bd, 'day', None)
                            month = getattr(bd, 'month', None)
                            year = getattr(bd, 'year', None)
                            if isinstance(bd, dict):
                                day = day or bd.get('day')
                                month = month or bd.get('month')
                                year = year or bd.get('year')
                            if day and month:
                                birthdate_str = f"{int(month):02d}-{int(day):02d}"
                                if year:
                                    birthdate_str = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
                        except Exception:
                            birthdate_str = None
                    # Точечная отладка для проверки полей дня рождения (по умолчанию выключена)
                    try:
                        if DEBUG_BIRTHDAY_LOGS and not birthdate_str:
                            attrs = [a for a in dir(full_user) if not a.startswith('_')]
                            logging.info("[DBG] full_user attrs: %s", attrs)
                            maybe_bd = None
                            for a in ('birthday','birthdate','birth_date'):
                                if hasattr(full_user, a):
                                    maybe_bd = getattr(full_user, a)
                                    break
                            logging.info("[DBG] birthday object: %r", maybe_bd)
                            if maybe_bd is not None:
                                logging.info("[DBG] birthday fields: day=%s month=%s year=%s", getattr(maybe_bd,'day',None), getattr(maybe_bd,'month',None), getattr(maybe_bd,'year',None))
                    except Exception:
                        pass
                except Exception:
                    # Молча игнорируем, если библиотека/поле недоступны или приватность запрещает
                    pass

                # Доп. попытка получить last_name через get_users (более полный объект)
                last_name = getattr(user, 'last_name', None)
                try:
                    if not last_name:
                        detailed = await client.get_users(user.id)
                        ln = getattr(detailed, 'last_name', None)
                        if ln:
                            last_name = ln
                except Exception:
                    pass

                # Если Pyrogram не дал дату рождения — пробуем Telethon (если авторизован)
                if not birthdate_str:
                    try:
                        birthdate_str = await _telethon_fetch_birthdate(user.id, (user.username or ''))
                    except Exception:
                        pass

                user_data = {
                    'user_id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': last_name,
                    'birthdate': birthdate_str,
                    'phone': getattr(user, 'phone_number', None),
                    'is_bot': user.is_bot,
                    'is_verified': getattr(user, 'is_verified', False),
                    'is_premium': getattr(user, 'is_premium', False),
                    'language_code': getattr(user, 'language_code', None),
                    'join_date': datetime.now(),
                    'status': 'active'
                }
                subscribers.append(user_data)
        
        logging.info(f"📊 Получено {len(subscribers)} реальных подписчиков")
        return subscribers
        
    except ImportError:
        logging.error("❌ Pyrogram не установлен: pip install pyrogram tgcrypto")
        return []
    except Exception as e:
        logging.error(f"❌ Ошибка получения подписчиков: {e}")
        return []

def save_subscriber(subscriber):
    """Сохраняет подписчика в БД"""
    try:
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO subscribers 
            (user_id, username, first_name, last_name, birthdate)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            subscriber.get('user_id'),
            subscriber.get('username'),
            subscriber.get('first_name'),
            subscriber.get('last_name'),
            subscriber.get('birthdate'),
        ))

        conn.commit()
        conn.close()

    except Exception as e:
        logging.error(f"❌ Ошибка сохранения подписчика: {e}")

async def send_welcome_to_subscriber(subscriber):
    """Отправляет приветствие подписчику"""
    try:
        # Формируем имя для приветствия
        name = subscriber['username'] if subscriber['username'] else subscriber['first_name'] or "друг"
        if name != "друг" and not name.startswith('@'):
            name = f"@{name}"
        
        # Выбираем случайное приветственное сообщение от Versavija
        welcome_text = random.choice(WELCOME_MESSAGES).format(name=name)
        
        logging.info(f"🔄 Попытка отправки приветствия для {name}...")
        
        # Отправляем в канал через Bot API (используем ID)
        await bot.send_message(TARGET_CHANNEL_ID, welcome_text)
        
        logging.info(f"✅ Приветствие отправлено для {name}")
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка отправки приветствия для {name if 'name' in locals() else 'неизвестного пользователя'}: {e}")
        logging.error(f"❌ Тип ошибки: {type(e).__name__}")
        return False

async def sync_subscribers():
    """Синхронизация подписчиков"""
    logging.info("🔄 Начинаю синхронизацию подписчиков...")
    
    try:
        # Получаем текущих подписчиков
        current_subscribers = await get_channel_subscribers_simple()
        if not current_subscribers:
            logging.warning("⚠️ Не удалось получить список подписчиков")
            return
        
        # Получаем известных подписчиков из БД
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM subscribers')
        known_ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        # Находим новых подписчиков
        new_subscribers = []
        current_user_ids = {subscriber['user_id'] for subscriber in current_subscribers}
        
        for subscriber in current_subscribers:
            # Сохраняем всех подписчиков
            save_subscriber(subscriber)

            # Проверяем, новый ли это подписчик
            if subscriber['user_id'] not in known_ids:
                new_subscribers.append(subscriber)
        
        # Удаляем отписавшихся пользователей из базы данных
        unsubscribed_ids = known_ids - current_user_ids
        if unsubscribed_ids:
            logging.info(f"📤 Обнаружено {len(unsubscribed_ids)} отписавшихся пользователей")
            try:
                conn = sqlite3.connect('data.db')
                cursor = conn.cursor()
                for user_id in unsubscribed_ids:
                    cursor.execute('DELETE FROM subscribers WHERE user_id = ?', (user_id,))
                    logging.info(f"➖ Удален отписавшийся пользователь ID: {user_id}")
                conn.commit()
                conn.close()
            except Exception as e:
                logging.error(f"❌ Ошибка удаления отписавшихся: {e}")
        
        if new_subscribers:
            logging.info(f"🎉 Обнаружено {len(new_subscribers)} новых подписчиков!")
            
            # Отправляем приветствия новым подписчикам СРАЗУ
            for subscriber in new_subscribers:
                name = subscriber['username'] or subscriber['first_name'] or "новый подписчик"
                user_id = subscriber['user_id']
                
                logging.info(f"➕ Новый подписчик: {name} (ID: {user_id})")
                
                # Отправляем приветствие сразу
                success = await send_welcome_to_subscriber(subscriber)
                if success:
                    logging.info(f"📨 Приветствие мгновенно отправлено для {name}")
                else:
                    logging.error(f"❌ Не удалось отправить приветствие для {name}")
        else:
            logging.info("📊 Новых подписчиков не обнаружено")
            
    except Exception as e:
        logging.error(f"❌ Ошибка синхронизации: {e}")

async def process_pending_welcomes():
    """Обрабатывает отложенные приветствия"""
    global pending_welcomes
    
    if not pending_welcomes:
        return  # Нет отложенных приветствий
        
    logging.info(f"🔍 Проверяем {len(pending_welcomes)} отложенных приветствий...")
    
    current_time = datetime.now()
    to_remove = []
    
    for user_id, data in pending_welcomes.items():
        welcome_time = data['welcome_time']
        time_left = (welcome_time - current_time).total_seconds()
        
        logging.info(f"⏰ Пользователь {user_id}: осталось {time_left:.1f}с до отправки приветствия")
        
        if current_time >= welcome_time:
            # Время отправить приветствие
            logging.info(f"🚀 Отправляю приветствие пользователю {user_id}...")
            success = await send_welcome_to_subscriber(data['subscriber'])
            if success:
                logging.info(f"📨 Приветствие отправлено с задержкой {WELCOME_DELAY}с")
            to_remove.append(user_id)
    
    # Удаляем обработанные приветствия
    for user_id in to_remove:
        del pending_welcomes[user_id]
        logging.info(f"✅ Пользователь {user_id} удален из очереди приветствий")

async def subscriber_monitoring_task():
    """Основная задача мониторинга подписчиков"""
    while True:
        try:
            # Синхронизируем подписчиков
            await sync_subscribers()
            
            # Ждем до следующей проверки (30 секунд)
            await asyncio.sleep(30)
            
        except Exception as e:
            logging.error(f"❌ Ошибка в мониторинге: {e}")
            await asyncio.sleep(60)  # При ошибке ждем минуту

async def setup_simple_tracking():
    """Настройка упрощенного отслеживания"""
    logging.info("🎯 Настройка системы отслеживания подписчиков...")
    
    # Создаем таблицы БД
    create_subscribers_table()
    
    # Загружаем известных подписчиков
    try:
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM subscribers')
        global known_subscribers
        known_subscribers = {row[0] for row in cursor.fetchall()}
        conn.close()
        logging.info(f"📚 Загружено {len(known_subscribers)} известных подписчиков из БД")
    except:
        pass
    
    # Запускаем мониторинг
    asyncio.create_task(subscriber_monitoring_task())
    
    logging.info("✅ Система отслеживания подписчиков готова!")
    

## Admin command '/sync_subscribers' removed by request

if __name__ == "__main__":
    print("🎯 ПРОСТАЯ СИСТЕМА ОТСЛЕЖИВАНИЯ ПОДПИСЧИКОВ")
    print("="*50)
    print("⚡ Полностью автоматическая авторизация")
    print("📊 Реальные данные подписчиков")
    print("🎯 Именные приветствия с задержкой")
    asyncio.run(setup_simple_tracking())