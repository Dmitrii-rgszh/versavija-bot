import asyncio
import logging
import pathlib
import json
import os
from collections import Counter
from typing import Awaitable, Callable, Optional

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramRetryAfter,
)
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import db_async
from bot_constants import DEFAULT_MENU, MENU_MESSAGES

from config import bot, dp
from config import DEFAULT_CITY_NAME, DEFAULT_CITY_CENTER, MAP_ZOOM_DEFAULT
from utils import yandex_link_for_city, parse_yandex_coords, resolve_yandex_url, fetch_yandex_coords_from_html, parse_plain_coords, reverse_geocode_nominatim, parse_yandex_address_from_url, fetch_yandex_address_from_html
from admin_state import ADMIN_PENDING_ACTIONS
from admin_utils import is_admin_view_enabled, user_is_admin
from booking_handlers import inject_booking_status_button, catch_yandex_link
from db import (
    get_setting,
    set_setting,
    save_menu,
    get_pending_actions,
    save_pending_actions,
    add_user,
    get_all_users,
    add_promotion,
    get_active_promotions,
    get_all_promotions,
    delete_promotion,
    cleanup_expired_promotions,
)
from portfolio_handlers import handle_portfolio_pending_action
from content_handlers import handle_content_pending_action
from keyboards import (
    build_main_keyboard_from_menu,
    admin_panel_keyboard,
    build_category_admin_keyboard,
    build_category_delete_keyboard,
    build_category_photo_nav_keyboard,
    build_category_delete_viewer_keyboard,
    build_categories_admin_root_keyboard,
    build_confirm_delete_category_kb,
    build_undo_category_delete_kb,
    build_undo_photo_delete_kb,
    build_add_photos_in_progress_kb,
    build_confirm_delete_all_photos_kb,
    build_services_keyboard,
    build_wedding_packages_nav_keyboard,
    broadcast_confirm_keyboard,
    build_broadcast_image_keyboard,
    build_broadcast_confirm_keyboard,
    build_promotions_keyboard,
    build_add_promotion_keyboard,
    build_promotion_date_keyboard,
    build_promotion_image_keyboard,
)

WELCOME_TEXT = (
    "👇 Выберите действие:"
)

# Единые сообщения для меню с эмодзи 👇
BROADCAST_BATCH_SIZE = 20
BROADCAST_BATCH_DELAY = 1.0
BROADCAST_PER_MESSAGE_DELAY = 0.05
BROADCAST_MAX_RETRIES = 2


class BroadcastStates(StatesGroup):
    awaiting_text = State()
    awaiting_image = State()
    confirming = State()


async def _set_static_commands() -> None:
    try:
        await bot.delete_my_commands()
        await bot.set_my_commands([
            BotCommand(command='start', description='Главное меню'),
            BotCommand(command='portfolio', description='📸 Портфолио'),
            BotCommand(command='services', description='💰 Услуги и цены'),
            BotCommand(command='booking', description='📅 Запись'),
            BotCommand(command='promotions', description='🎉 Акции'),
            BotCommand(command='reviews', description='⭐ Отзывы'),
            BotCommand(command='social', description='📱 Соцсети'),
            BotCommand(command='adminmode_on', description='Включить админ-режим'),
            BotCommand(command='adminmode_off', description='Выключить админ-режим'),
        ])
    except Exception:
        logging.exception('Failed to set bot commands')

# Wedding packages data
WEDDING_PACKAGES = [
    {
        "title": "ПАКЕТ 1",
        "text": """ПРАЙС СВАДЕБНЫЙ🤵👰
ПАКЕТ 1 
 
- консультация на этапе подготовки к свадьбе 
- репортажная и художественная съемка в течении 3-х часов.
- профессиональная обработка фото:
15-ретушь
60-70 цветокоррекция.
 
-превью из 10 фотографий в течении 2-7 дней после свадьбы 
- получение фото через яндекс диск или на вашем носителе.
- срок на обработку 2,5 н. - 1 мес.

18000р 
 
* каждый следующий час съемки - 6000 р 
** в стоимость пакета включен трансфер фотографа на мероприятие и после, во время - передвигается с молодожёнами"""
    },
    {
        "title": "ПАКЕТ 2",
        "text": """ПРАЙС СВАДЕБНЫЙ🤵👰
ПАКЕТ 2 
 
- консультация на этапе подготовки к свадьбе 
- репортажная и художественная съемка в течении 5 часов 
- профессиональная обработка фото:
25 - ретушь.
100-120 цветокоррекция
- превью из 10 фотографий в течении 7 дней после свадьбы 
- получение фото через яндекс диск или на вашем носителе ( все обработанные фото )
- срок на обработку 3 н. - 1,5 мес. ( В зависимости от загруженности).

25.000 р 
 
* каждый следующий час съемки - 5.000 р 
** в стоимость пакета включен трансфер фотографа на мероприятие и после, во время - передвигается с молодожёнами"""
    },
    {
        "title": "ПАКЕТ 3",
        "text": """ПРАЙС СВАДЕБНЫЙ🤵👰
ПАКЕТ 3 
 
- консультация на этапе подготовки к свадьбе 
- репортажная и художественная съемка в течении 8 часов 
- профессиональная обработка фото:
40 - ретушь
150-160 цветокоррекция

- превью из 10 фотографий в течении недели после свадьбы 
- получение фото через яндекс диск или на вашем носителе ( все обработанные фото) - срок на обработку 1 - 2 месяц. 
 
35000 р 
 
** каждый следующий час съемки - 6000 р 
*** в стоимость пакета включен трансфер фотографа на мероприятие и после, во время - передвигается с молодожёнами"""
    },
    {
        "title": "ПАКЕТ 4",
        "text": """ПРАЙС СВАДЕБНЫЙ🤵👰
ПАКЕТ 4 
 
"Полный день +" 
 
- консультация на этапе подготовки к свадьбе 
- репортажная и художественная съёмка в течении 12 часов 
- профессиональная обработка фото:
60 ретушь
300 цветокоррекция.
- превью из 20 фотографий в течении 10 дней после свадьбы 
- получение фото через яндекс диск или на вашем носителе ( все обработанные фото)
- срок на обработку 1,5 - 2,5 месяца. 
 
62.000 р 
 
* съемка LoveStory в ПОДАРОК 
** каждый следующий час съемки - 6000 р 
*** в стоимость пакета включен трансфер фотографа на мероприятие и после, во время - передвигается с молодоженами"""
    }
]

# Lingerie service information
LINGERIE_SERVICE = {
    "title": "Lingerie (будуарная)",
    "text": """💋 Lingerie (будуарная).

7.000 рублей

1 час фотосъемки.
2 образа
Консультация на этапе подготовке к съемке
Подбор мест для фотосессий 
30-35 кадров в авторской обработке
10 кадров в ретуши.
Я помогу вам с подбором стилизации фотосессии и позированием
Аренда студии оплачивается отдельно 
Закрытый доступ к фотографиям на облачном диске
 
❗️Бронь фотосессии осуществляется после предоплаты.

Готовые фотографии в течение 14 рабочих дня."""
}

# Reportage service information  
REPORTAGE_SERVICE = {
    "title": "Репортажная",
    "text": """📸 Репортажная 

От 3.000 рублей за час
В зависимости от места проведения фотосессии.
От 30 и до 50 в авторской обработке.
5 кадров в ретуши.
Закрытый доступ к фотографиям на облачном диске.

❗️Бронь фотосессии осуществляется после предоплаты.

Готовые фотографии в течение 14 рабочих дня."""
}

# Common service text for individual categories
_COMMON_SERVICE_TEXT = """Прайс
5.000 рублей

1 час фотосъемки.
2 образа
Консультация на этапе подготовке к съемке
Подбор мест для фотосессий
30-35 кадров в авторской обработке
5 кадра в ретуши.
Я помогу вам с подбором стилизации фотосессии и позированием
Аренда студии оплачивается отдельно
Закрытый доступ к фотографиям на облачном диске

❗️Бронь фотосессии осуществляется после предоплаты.
Готовые фотографии в течение 14 рабочих дня."""

# Individual service information
INDIVIDUAL_SERVICE = {
    "title": "Индивидуальная",
    "text": f"👤 Индивидуальная\n\n{_COMMON_SERVICE_TEXT}"
}

# Mom and child service information
MOM_CHILD_SERVICE = {
    "title": "Мама и ребенок",
    "text": f"👩‍👶 Мама и ребенок\n\n{_COMMON_SERVICE_TEXT}"
}

# Love story service information
LOVE_STORY_SERVICE = {
    "title": "Love Story",
    "text": f"💕 Love Story\n\n{_COMMON_SERVICE_TEXT}"
}

# Family service information
FAMILY_SERVICE = {
    "title": "Семейная",
    "text": f"👨‍👩‍👧‍👦 Семейная\n\n{_COMMON_SERVICE_TEXT}"
}

# Children service information
CHILDREN_SERVICE = {
    "title": "Детская (садики/школы)",
    "text": f"🧒 Детская (садики/школы)\n\n{_COMMON_SERVICE_TEXT}"
}

# временное состояние для ожидающих действий админа: username -> action
# persisted to DB so flow survives restarts
try:
    ADMIN_PENDING_ACTIONS: dict = get_pending_actions()
    if ADMIN_PENDING_ACTIONS:
        legacy = [
            key
            for key, value in list(ADMIN_PENDING_ACTIONS.items())
            if (
                (isinstance(value, dict) and value.get('action') in {'broadcast_text', 'broadcast_image'})
                or (isinstance(value, str) and value.startswith('broadcast'))
            )
        ]
        if legacy:
            for key in legacy:
                ADMIN_PENDING_ACTIONS.pop(key, None)
            save_pending_actions(ADMIN_PENDING_ACTIONS)
except Exception:
    # If DB not initialized yet, use empty dict
    ADMIN_PENDING_ACTIONS: dict = {}
## Admin commands removed by request: /adminmode and refresh/sync commands


@dp.message(Command(commands=['start']))
async def send_welcome(message: Message):
    username = (message.from_user.username or "").lstrip("@").lower()
    user_id = message.from_user.id
    
    # Save user to database for broadcast functionality
    await db_async.add_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )
    
    is_admin = await is_admin_view_enabled(username, user_id)
    # load menu from DB (default menu if none)
    menu = await db_async.get_menu(DEFAULT_MENU)
    keyboard = build_main_keyboard_from_menu(menu, is_admin)
    keyboard = await inject_booking_status_button(keyboard, user_id)
    await _set_static_commands()

    # Отправляем фото приветствия с меню в одном сообщении
    image_file_id = await db_async.get_setting('welcome_image_file_id', None)
    
    # если в БД есть file_id — отправляем фото с кнопками
    if image_file_id:
        try:
            await message.answer_photo(
                photo=image_file_id, 
                caption=MENU_MESSAGES["main"], 
                reply_markup=keyboard
            )
            return  # Успешно отправили, выходим
        except Exception:
            logging.exception('Failed to send photo by file_id, will try local file')
    
    # Fallback to local file
    media_path = pathlib.Path(__file__).parent / 'media' / 'greetings.png'
    if media_path.exists():
        photo = FSInputFile(pathlib.Path(media_path))
        try:
            await message.answer_photo(
                photo=photo, 
                caption=MENU_MESSAGES["main"], 
                reply_markup=keyboard
            )
            return  # Успешно отправили, выходим
        except Exception:
            logging.exception('Failed to send local photo')

    # Если не удалось отправить фото, отправляем только текст с кнопками
    try:
        await message.answer(MENU_MESSAGES["main"], reply_markup=keyboard)
        logging.info("Text menu sent to chat %s (user=%s)", message.chat.id, username)
    except Exception:
        logging.exception("Failed to send menu message")


    # End of send_welcome

@dp.message(Command(commands=['get_chat_id']))  
async def get_chat_id_command(message: Message):
    """Показывает ID текущего чата - полезно для настройки новой группы"""
    try:
        chat_info = await message.bot.get_chat(message.chat.id)
        
        result = f"""🆔 **Информация о чате:**

**ID:** `{message.chat.id}`
**Тип:** {chat_info.type}
**Название:** {chat_info.title or 'Без названия'}
**Username:** @{chat_info.username or 'Нет username'}

💡 **Для welcome messages используйте:**
```python
TARGET_GROUP_ID = {message.chat.id}
```

🔧 **Статус чата:**
• {'✅ Подходит для приветствий' if chat_info.type in ['group', 'supergroup'] else '❌ Каналы не поддерживают приветствия'}
"""
        
        await message.reply(result, parse_mode="Markdown")
        
    except Exception as e:
        await message.reply(f"❌ Ошибка получения информации о чате: {e}")


async def update_promotion_message(query, promotion_idx: int, promotions: list, is_admin: bool = False):
    """Update existing promotion message with navigation."""
    if not promotions:
        await query.message.edit_text("🎉 На текущий момент нет действующих акций.")
        return
    
    # Ensure valid index
    if promotion_idx >= len(promotions):
        promotion_idx = 0
    elif promotion_idx < 0:
        promotion_idx = len(promotions) - 1
    
    promotion = promotions[promotion_idx]
    promo_id, title, description, image_file_id, start_date, end_date, created_by = promotion
    
    # Format the message
    from datetime import datetime
    try:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        formatted_end_date = end_date_obj.strftime('%d.%m.%Y')
    except:
        formatted_end_date = end_date
    
    text = f"🎉 {title}\n\n{description}\n\n📅 Акция действует до {formatted_end_date}"
    
    if len(promotions) > 1:
        text += f"\n\n📄 {promotion_idx + 1} из {len(promotions)}"
    
    kb = build_promotions_keyboard(promotion_idx, is_admin)
    
    # Check if the current message has photo
    current_has_photo = query.message.photo is not None
    new_has_photo = image_file_id is not None
    
    try:
        if current_has_photo and new_has_photo:
            # Both current and new message have photos - update media
            from aiogram.types import InputMediaPhoto
            media = InputMediaPhoto(media=image_file_id, caption=text)
            await query.message.edit_media(media=media, reply_markup=kb)
        elif current_has_photo and not new_has_photo:
            # Current has photo, new doesn't - delete current and send text message
            await query.message.delete()
            from config import bot
            await bot.send_message(chat_id=query.message.chat.id, text=text, reply_markup=kb)
        elif not current_has_photo and new_has_photo:
            # Current is text, new has photo - delete current and send photo message
            await query.message.delete()
            from config import bot
            await bot.send_photo(chat_id=query.message.chat.id, photo=image_file_id, caption=text, reply_markup=kb)
        else:
            # Both are text messages - edit text
            await query.message.edit_text(text, reply_markup=kb)
    except Exception as e:
        logging.warning(f"Failed to update promotion message: {e}")
        # Fallback: delete current message and send new one
        try:
            await query.message.delete()
            from config import bot
            if image_file_id:
                await bot.send_photo(chat_id=query.message.chat.id, photo=image_file_id, caption=text, reply_markup=kb)
            else:
                await bot.send_message(chat_id=query.message.chat.id, text=text, reply_markup=kb)
        except Exception as e2:
            logging.error(f"Fallback also failed: {e2}")
            # Last resort: just edit the text without image
            try:
                await query.message.edit_text(text, reply_markup=kb)
            except:
                pass


async def show_promotion(message, promotion_idx: int, promotions: list = None, is_admin: bool = False):
    """Show a specific promotion with navigation."""
    if promotions is None:
        promotions = get_active_promotions()
    
    if not promotions:
        if is_admin:
            kb = build_add_promotion_keyboard()
            await message.answer(
                "🎉 На текущий момент нет действующих акций. Мы работаем над этим! 😊", 
                reply_markup=kb
            )
        else:
            await message.answer("🎉 На текущий момент нет действующих акций. Мы работаем над этим! 😊")
        return
    
    # Ensure valid index
    if promotion_idx >= len(promotions):
        promotion_idx = 0
    elif promotion_idx < 0:
        promotion_idx = len(promotions) - 1
    
    promotion = promotions[promotion_idx]
    promo_id, title, description, image_file_id, start_date, end_date, created_by = promotion
    
    # Format the message
    from datetime import datetime
    try:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        formatted_end_date = end_date_obj.strftime('%d.%m.%Y')
    except:
        formatted_end_date = end_date
    
    text = f"🎉 {title}\n\n{description}\n\n📅 Акция действует до {formatted_end_date}"
    
    if len(promotions) > 1:
        text += f"\n\n📄 {promotion_idx + 1} из {len(promotions)}"
    
    kb = build_promotions_keyboard(promotion_idx, is_admin)
    
    try:
        if image_file_id:
            await message.answer_photo(photo=image_file_id, caption=text, reply_markup=kb)
        else:
            await message.answer(text, reply_markup=kb)
    except Exception as e:
        logging.warning(f"Failed to send promotion: {e}")
        await message.answer(text, reply_markup=kb)


@dp.message(Command(commands=['services']))
async def cmd_services(message: Message):
    """Handle /services command"""
    kb = build_services_keyboard()
    await message.answer(MENU_MESSAGES["services"], reply_markup=kb)

@dp.message(Command(commands=['promotions']))
async def cmd_promotions(message: Message):
    """Handle /promotions command"""
    username = (message.from_user.username or "").lstrip("@").lower()
    
    # Cleanup expired promotions first
    cleanup_expired_promotions()
    
    # Get active promotions
    promotions = get_active_promotions()
    is_admin = await is_admin_view_enabled(username, message.from_user.id)
    
    if not promotions:
        # No active promotions
        if is_admin:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить акцию", callback_data="add_promotion")],
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_main")]
            ])
            await message.answer("🎉 На текущий момент нет действующих акций.\n\nВы можете добавить новую акцию:", reply_markup=kb)
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_main")]
            ])
            await message.answer("🎉 На текущий момент нет действующих акций.", reply_markup=kb)
        return
    
    # Show first promotion
    await show_promotion(message, 0, promotions, is_admin)

@dp.callback_query()
async def handle_callback(query: CallbackQuery, state: FSMContext):
    # Fix for UnboundLocalError: explicitly declare imported classes as global
    global InlineKeyboardMarkup, InlineKeyboardButton
    
    data_raw = query.data or ""
    data = data_raw.lower()
    username = (query.from_user.username or "").lstrip("@").lower()

    if data_raw and (data_raw == 'booking' or data.startswith('bk_') or data_raw == 'booking_status'):
        raise SkipHandler()

    if data_raw and (
        data_raw == 'portfolio'
        or data.startswith('pf_')
        or data.startswith('pf:')
        or data.startswith('like:')
    ):
        raise SkipHandler()

    if data_raw and (
        data_raw == 'reviews'
        or data_raw == 'social'
        or data_raw == 'social_edit'
        or data.startswith('reviews_')
    ):
        raise SkipHandler()

    # quick debug log to capture what callback data arrives from the client
    logging.info("HANDLER VERSION vDel2 | user=%s raw=%s lowered=%s", username, data_raw, data)

    try:
        await query.answer()
    except Exception:
        pass

    # public actions
    if data == "services":
        kb = build_services_keyboard()
        await query.message.answer(MENU_MESSAGES["services"], reply_markup=kb)
        return

    if data == "back_main":
        menu = await db_async.get_menu(DEFAULT_MENU)
        is_admin = await is_admin_view_enabled(username, query.from_user.id)
        kb = build_main_keyboard_from_menu(menu, is_admin)
        kb = await inject_booking_status_button(kb, query.from_user.id)
        await query.message.answer(MENU_MESSAGES["main"], reply_markup=kb)
        return

    if data == "promotions":
        # Cleanup expired promotions first
        cleanup_expired_promotions()
        
        # Get active promotions
        promotions = get_active_promotions()
        is_admin = await is_admin_view_enabled(username, query.from_user.id)
        
        if not promotions:
            # No active promotions
            if is_admin:
                kb = build_add_promotion_keyboard()
                await query.message.answer(
                    "🎉 На текущий момент нет действующих акций. Мы работаем над этим! 😊", 
                    reply_markup=kb
                )
            else:
                await query.message.answer("🎉 На текущий момент нет действующих акций. Мы работаем над этим! 😊")
            return
        
        # Show first promotion
        await show_promotion(query.message, 0, promotions, is_admin)
        return

    # Handle promotion navigation
    if data.startswith("promo_prev:") or data.startswith("promo_next:"):
        # Cleanup expired promotions first
        cleanup_expired_promotions()
        
        # Get active promotions
        promotions = get_active_promotions()
        is_admin = await is_admin_view_enabled(username, query.from_user.id)
        
        if not promotions:
            await query.message.answer("🎉 На текущий момент нет действующих акций.")
            return
        
        # Extract current index
        try:
            current_idx = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            current_idx = 0
        
        # Calculate new index
        if data.startswith("promo_prev:"):
            new_idx = (current_idx - 1) % len(promotions)
        else:  # promo_next
            new_idx = (current_idx + 1) % len(promotions)
        
        # Update the promotion message with new index
        try:
            await update_promotion_message(query, new_idx, promotions, is_admin)
        except Exception as e:
            # Fallback to first promotion if something goes wrong
            await update_promotion_message(query, 0, promotions, is_admin)
        return
    
    if data == "wedding_packages":
        # Show first wedding package
        package = WEDDING_PACKAGES[0]
        kb = build_wedding_packages_nav_keyboard(0)
        await query.message.answer(package["text"], reply_markup=kb)
        return
    
    if data == "lingerie_service":
        # Show lingerie service information
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Услуги", callback_data="services")]
        ])
        await query.message.answer(LINGERIE_SERVICE["text"], reply_markup=kb)
        return
    
    if data == "reportage_service":
        # Show reportage service information
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Услуги", callback_data="services")]
        ])
        await query.message.answer(REPORTAGE_SERVICE["text"], reply_markup=kb)
        return
    
    if data == "individual_service":
        # Show individual service information
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Услуги", callback_data="services")]
        ])
        await query.message.answer(INDIVIDUAL_SERVICE["text"], reply_markup=kb)
        return
    
    if data == "mom_child_service":
        # Show mom and child service information
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Услуги", callback_data="services")]
        ])
        await query.message.answer(MOM_CHILD_SERVICE["text"], reply_markup=kb)
        return
    
    if data == "love_story_service":
        # Show love story service information
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Услуги", callback_data="services")]
        ])
        await query.message.answer(LOVE_STORY_SERVICE["text"], reply_markup=kb)
        return
    
    if data == "family_service":
        # Show family service information
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Услуги", callback_data="services")]
        ])
        await query.message.answer(FAMILY_SERVICE["text"], reply_markup=kb)
        return
    
    if data == "children_service":
        # Show children service information
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Услуги", callback_data="services")]
        ])
        await query.message.answer(CHILDREN_SERVICE["text"], reply_markup=kb)
        return
    
    if data.startswith("wedding_pkg_prev:") or data.startswith("wedding_pkg_next:"):
        # Handle wedding package navigation
        try:
            if data.startswith("wedding_pkg_prev:"):
                current_idx = int(data.split(":", 1)[1])
                # Calculate previous index (cycle through packages backwards)
                next_idx = (current_idx - 1) % len(WEDDING_PACKAGES)
            else:  # wedding_pkg_next:
                current_idx = int(data.split(":", 1)[1])
                # Calculate next index (cycle through packages forward)
                next_idx = (current_idx + 1) % len(WEDDING_PACKAGES)
            
            package = WEDDING_PACKAGES[next_idx]
            kb = build_wedding_packages_nav_keyboard(next_idx)
            await query.message.edit_text(package["text"], reply_markup=kb)
        except (ValueError, IndexError):
            # Fallback to first package
            package = WEDDING_PACKAGES[0]
            kb = build_wedding_packages_nav_keyboard(0)
            await query.message.edit_text(package["text"], reply_markup=kb)
        return
    
    if data == "main_menu":
        # Return to main menu
        menu = await db_async.get_menu(DEFAULT_MENU)
        is_admin = await is_admin_view_enabled(username, query.from_user.id)
        keyboard = build_main_keyboard_from_menu(menu, is_admin)
        keyboard = await inject_booking_status_button(keyboard, query.from_user.id)
        await query.message.answer(MENU_MESSAGES["main"], reply_markup=keyboard)
        return
    
    # booking flow handled later (remove early stub)
async def perform_broadcast(text: str, image_file_id: str = None, message: Message = None):
    """Send broadcast message to all users."""
    async def _send_to_user(user_id: int) -> tuple[bool, Optional[str]]:
        """Helper that dispatches message/photo to конкретного пользователя."""

        async def _dispatch() -> None:
            if image_file_id:
                await bot.send_photo(user_id, image_file_id, caption=text)
            else:
                await bot.send_message(user_id, text)

        return await _broadcast_send_with_retry(user_id, _dispatch, max_retries=BROADCAST_MAX_RETRIES)

    users = await asyncio.to_thread(get_all_users)
    total = len(users)
    sent = 0
    failures = Counter()

    broadcast_type = "с изображением" if image_file_id else "только текст"
    if message:
        await message.answer(f"📤 Начинаю рассылку ({broadcast_type}) для {total} пользователей...")

    if total == 0:
        if message:
            await message.answer("ℹ️ В базе нет получателей для рассылки.")
        return

    for idx, (user_id, username, first_name, last_name) in enumerate(users, start=1):
        success, reason = await _send_to_user(user_id)
        if success:
            sent += 1
        else:
            failures[reason or 'unknown'] += 1

        # Плавное ограничение скорости: небольшая пауза между сообщениями
        if idx < total:
            if idx % BROADCAST_BATCH_SIZE == 0:
                await asyncio.sleep(BROADCAST_BATCH_DELAY)
            else:
                await asyncio.sleep(BROADCAST_PER_MESSAGE_DELAY)

    failed = total - sent

    summary_lines = [
        "✅ Рассылка завершена!",
        f"📨 Отправлено: {sent}",
        f"❌ Не доставлено: {failed}",
        f"📊 Всего пользователей: {total}",
    ]
    if failures:
        breakdown = ', '.join(f"{reason}: {count}" for reason, count in failures.most_common())
        summary_lines.append(f"ℹ️ Причины недоставки: {breakdown}")

    result_text = "\n".join(summary_lines)
    if message:
        await message.answer(result_text)


async def _broadcast_send_with_retry(
    user_id: int,
    dispatcher: Callable[[], Awaitable[None]],
    max_retries: int = 2,
) -> tuple[bool, Optional[str]]:
    """Отправить сообщение пользователю с учётом FloodWait/retry.

    Возвращает (success: bool, reason: str | None).
    """
    attempt = 0
    while True:
        try:
            await dispatcher()
            return True, None
        except TelegramRetryAfter as exc:
            attempt += 1
            if attempt > max_retries:
                logging.warning('FloodWait limit для %s: %s', user_id, exc)
                return False, 'flood_wait'
            delay = exc.retry_after + 0.5
            logging.info('FloodWait %ss при рассылке пользователю %s, повтор #%s', delay, user_id, attempt)
            await asyncio.sleep(delay)
        except (TelegramForbiddenError, TelegramNotFound) as exc:
            logging.info('Пользователь %s недоступен для рассылки: %s', user_id, exc)
            return False, 'unreachable'
        except TelegramBadRequest as exc:
            logging.warning('Неверный запрос при рассылке пользователю %s: %s', user_id, exc)
            return False, 'bad_request'
        except Exception as exc:
            attempt += 1
            logging.warning('Ошибка рассылки пользователю %s (попытка %s/%s): %s', user_id, attempt, max_retries + 1, exc)
            if attempt > max_retries:
                return False, exc.__class__.__name__.lower()
            await asyncio.sleep(1.0)


@dp.message()
async def handle_admin_pending(message: Message, state: FSMContext):
    username = (message.from_user.username or "").lstrip("@").lower()
    # allow only if admin mode ON (else ignore silently)
    if not await is_admin_view_enabled(username, message.from_user.id):
        return

    current_state = await state.get_state()
    if current_state in BroadcastStates.__all_states__:
        # Обработка рассылки выполняется отдельными хендлерами
        return

    try:
        pend_raw = await db_async.get_setting(f'pending_booking_{message.from_user.id}', None)
        if pend_raw:
            pend = json.loads(pend_raw)
        else:
            pend = None
    except Exception:
        pend = None
    if isinstance(pend, dict) and pend.get('await_loc'):
        await catch_yandex_link(message)
        return

    action = ADMIN_PENDING_ACTIONS.get(username)
    if not action:
        return



    # Handle different action types
    if action and isinstance(action, dict):
        a = action.get('action')
        payload = action.get('payload', {})
    elif action and isinstance(action, str):
        # Handle old string format (for backward compatibility)
        a = action
        payload = {}
    else:
        return

    # Process other admin actions
    a = action.get('action')
    payload = action.get('payload', {})
    logging.info('Admin pending action for %s: %s', username, a)

    if await handle_portfolio_pending_action(message, username, a, payload):
        return
    if await handle_content_pending_action(message, username, a, payload):
        return
    # --- Photo/category & menu editing handlers (single consolidated block) ---
    # Promotion management cases
    if a == 'add_promotion_title':
        if not message.text:
            await message.answer('❌ Ожидаю текст заголовка акции. Попробуйте снова.')
            return
        title = message.text.strip()
        if not title:
            await message.answer('❌ Заголовок не может быть пустым. Попробуйте снова.')
            return
        
        ADMIN_PENDING_ACTIONS[username] = {'action': 'add_promotion_description', 'payload': {'title': title}}
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await message.answer(f'✅ Заголовок сохранён: "{title}"\n\n📝 Теперь пришлите описание акции:')
        return
    
    if a == 'add_promotion_description':
        if not message.text:
            await message.answer('❌ Ожидаю текст описания акции. Попробуйте снова.')
            return
        description = message.text.strip()
        if not description:
            await message.answer('❌ Описание не может быть пустым. Попробуйте снова.')
            return
        
        title = payload.get('title')
        ADMIN_PENDING_ACTIONS[username] = {
            'action': 'add_promotion_image', 
            'payload': {'title': title, 'description': description}
        }
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await message.answer(f'✅ Описание сохранено\n\n🖼️ Теперь пришлите изображение для акции:', reply_markup=build_promotion_image_keyboard())
        return
    
    if a == 'add_promotion_image':
        title = payload.get('title')
        description = payload.get('description')
        image_file_id = None
        
        # Handle image
        photo = None
        if message.photo:
            photo = message.photo[-1]
        elif message.document and message.document.mime_type and message.document.mime_type.startswith('image'):
            image_file_id = message.document.file_id
        
        if photo:
            image_file_id = photo.file_id
        
        if not image_file_id:
            await message.answer('❌ Ожидаю изображение. Используйте кнопку "Без фото" если хотите создать акцию без изображения.')
            return
        
        ADMIN_PENDING_ACTIONS[username] = {
            'action': 'add_promotion_start_date', 
            'payload': {'title': title, 'description': description, 'image_file_id': image_file_id}
        }
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        from datetime import datetime
        await message.answer('✅ Изображение сохранено\n\n📅 Выберите дату начала акции:', reply_markup=build_promotion_date_keyboard(datetime.now().year, datetime.now().month, 'promo_start_date'))
        return
    
    if a == 'add_promotion_start_date':
        # This will be handled by callback, not text message
        await message.answer('📅 Используйте кнопки календаря для выбора даты начала акции.')
        return
    
    if a == 'add_promotion_end_date':
        # This will be handled by callback, not text message
        await message.answer('📅 Используйте кнопки календаря для выбора даты окончания акции.')
        return
