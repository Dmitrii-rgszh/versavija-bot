import logging
import pathlib
import json
import os
from pathlib import Path
from typing import Optional

# track last shown photo index per chat+category to avoid repeats
LAST_CATEGORY_PHOTO: dict[tuple[int, str], int] = {}
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from aiogram.filters import Command

from config import bot, dp, ADMIN_IDS
from db import get_setting, set_setting, get_menu, save_menu, get_pending_actions, save_pending_actions
from db import add_booking, is_slot_taken, get_bookings_between, get_booking, update_booking_status, clear_all_bookings
from db import get_active_booking_for_user, update_booking_time_and_category, add_user, get_all_users
from db import add_promotion, get_active_promotions, get_all_promotions, delete_promotion, cleanup_expired_promotions
from db import toggle_photo_like, get_photo_likes_count, user_has_liked_photo
from keyboards import (
    build_main_keyboard_from_menu,
    admin_panel_keyboard,
    build_portfolio_keyboard,
    build_category_admin_keyboard,
    build_category_delete_keyboard,
    build_category_photo_nav_keyboard,
    build_category_delete_viewer_keyboard,
    build_categories_admin_root_keyboard,
    build_confirm_delete_category_kb,
    build_undo_category_delete_kb,
    build_social_admin_keyboard,
    build_reviews_nav_keyboard,
    build_reviews_admin_keyboard,
    build_reviews_delete_keyboard,
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
    ADMIN_USERNAMES,
)

# In-memory state containers (not persisted unless explicitly written via set_setting)
BOOKING_FLOW_MSGS: dict[int, list[int]] = {}
UNDO_DELETED_CATEGORY: dict[str, dict] = {}
UNDO_DELETED_CATEGORY_PHOTOS: dict[str, list] = {}
UNDO_DELETED_PHOTO: dict[str, str] = {}

WELCOME_TEXT = (
    "👇 Выберите действие:"
)

# Единые сообщения для меню с эмодзи 👇
MENU_MESSAGES = {
    "main": "👇 Выберите действие:",
    "portfolio": "👇 Выберите категорию портфолио:",
    "services": "👇 Выберите категорию услуг:",
    "booking": "👇 Выберите категорию фотосессии:",
    "admin": "👇 Выберите действие администрирования:",
    "delete_photo": "👇 Выберите фото для удаления:",
    "delete_review": "👇 Выберите отзыв для удаления:",
    "select_date": "👇 Выберите дату:",
}

# default menu used when DB has no saved menu
DEFAULT_MENU = [
    {"text": "📸 Портфолио", "callback": "portfolio"},
    {"text": "💰 Услуги и цены", "callback": "services"},
    {"text": "📅 Онлайн-запись", "callback": "booking"},
    {"text": "🎉 Акции", "callback": "promotions"},
    {"text": "⭐ Отзывы", "callback": "reviews"},
    {"text": "📱 Соцсети", "callback": "social"},
]

# default portfolio categories
DEFAULT_PORTFOLIO_CATEGORIES = [
    {"text": "👨‍👩‍👧‍👦 Семейная", "slug": "family"},
    {"text": "💕 Love Story", "slug": "love_story"},
    {"text": "👤 Индивидуальная", "slug": "personal"},
    {"text": "🎉 Репортажная (банкеты, мероприятия)", "slug": "reportage"},
    {"text": "� Свадебная", "slug": "wedding"},
    {"text": "💋 Lingerie (будуарная)", "slug": "lingerie"},
    {"text": "👶 Детская (школы/садики)", "slug": "children"},
    {"text": "👩‍👶 Мама с ребёнком", "slug": "mom_child"},
    {"text": "✝️ Крещение", "slug": "baptism"},
    {"text": "⛪ Венчание", "slug": "wedding_church"},
]

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

# IDs of users for whom we show dynamic booking status button (can be extended)
def _load_booking_status_user_ids() -> set[int]:
    try:
        raw = get_setting('booking_status_user_ids', '') or ''
        ids = set()
        for part in raw.split(','):
            part = part.strip()
            if part.isdigit():
                ids.add(int(part))
        return ids
    except Exception:
        # If DB not initialized yet, return empty set
        return set()

BOOKING_STATUS_USER_IDS = _load_booking_status_user_ids()

def _add_booking_status_user(user_id: int):
    raw = get_setting('booking_status_user_ids', '') or ''
    parts = [p.strip() for p in raw.split(',') if p.strip()]
    if str(user_id) not in parts:
        parts.append(str(user_id))
        set_setting('booking_status_user_ids', ','.join(parts))


async def _set_static_commands():
    try:
        await bot.set_my_commands([
            BotCommand(command='start', description='Главное меню'),
            BotCommand(command='portfolio', description='📸 Портфолио'),
            BotCommand(command='services', description='💰 Услуги и цены'),
            BotCommand(command='booking', description='📅 Онлайн-запись'),
            BotCommand(command='promotions', description='🎉 Акции'),
            BotCommand(command='reviews', description='⭐ Отзывы'),
            BotCommand(command='social', description='📱 Соцсети'),
            BotCommand(command='adminmode', description='Админ режим'),
        ])
    except Exception as e:
        logging.warning('Failed to set static commands: %s', e)

def _inject_booking_status_button(kb: InlineKeyboardMarkup, user_id: int) -> InlineKeyboardMarkup:
    """If user has any active booking, prepend status button (no manual whitelist needed)."""
    booking = get_active_booking_for_user(user_id)
    if not booking:
        return kb
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(booking['start_ts'])
        label = f"✅Вы записаны: {dt.strftime('%H:%M %d.%m.%Y')}"
    except Exception:
        label = "✅ Вы записаны"
    rows = list(kb.inline_keyboard)
    if any(r and any(btn.callback_data == 'booking_status' for btn in r) for r in rows):
        return kb
    rows.insert(0, [InlineKeyboardButton(text=label, callback_data='booking_status')])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_portfolio_categories() -> list:
    raw = get_setting('portfolio_categories', None)
    if raw:
        try:
            cats = json.loads(raw)
            if isinstance(cats, list) and cats:
                return cats
        except Exception:
            pass
    # save defaults if none
    set_setting('portfolio_categories', json.dumps(DEFAULT_PORTFOLIO_CATEGORIES, ensure_ascii=False))
    return DEFAULT_PORTFOLIO_CATEGORIES

# временное состояние для ожидающих действий админа: username -> action
# persisted to DB so flow survives restarts
try:
    ADMIN_PENDING_ACTIONS: dict = get_pending_actions()
except Exception:
    # If DB not initialized yet, use empty dict
    ADMIN_PENDING_ACTIONS: dict = {}


def _user_is_admin(username: str, user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    return username in ADMIN_USERNAMES


def _add_known_admin(user_id: int):
    """Persist admin user_id so we can notify later (for username-based admins)."""
    try:
        raw = get_setting('admin_known_ids', '') or ''
        ids = {int(x) for x in raw.split(',') if x.strip().isdigit()}
        if user_id not in ids:
            ids.add(user_id)
            set_setting('admin_known_ids', ','.join(str(i) for i in sorted(ids)))
    except Exception:
        pass


def _get_all_admin_ids() -> set[int]:
    ids: set[int] = set(ADMIN_IDS)
    try:
        raw = get_setting('admin_known_ids', '') or ''
        for part in raw.split(','):
            part = part.strip()
            if part.isdigit():
                ids.add(int(part))
    except Exception:
        pass
    return ids


def is_admin_view_enabled(username: str, user_id: int) -> bool:
    if not _user_is_admin(username, user_id):
        return False
    val = get_setting(f'admin_mode_{user_id}', 'on') or 'on'
    return val == 'on'


@dp.message(Command(commands=['adminmode']))
async def toggle_admin_mode(message: Message):
    username = (message.from_user.username or '').lstrip('@').lower()
    user_id = message.from_user.id
    if not _user_is_admin(username, user_id):
        return await message.answer('🚫 Нет доступа.')
    # ensure this admin is remembered for future notifications
    _add_known_admin(user_id)
    key = f'admin_mode_{user_id}'
    cur = get_setting(key, 'on') or 'on'
    new_val = 'off' if cur == 'on' else 'on'
    set_setting(key, new_val)
    state_text = 'ВЫКЛЮЧЕН' if new_val == 'off' else 'ВКЛЮЧЕН'
    # покажем уведомление о смене режима
    await message.answer(f'🔁 Режим администратора теперь: {state_text}.')
    # после переключения всегда показываем приветственный экран как «перезагрузку» интерфейса
    # (импортируем локально, чтобы не создавать циклическую зависимость при импорте вверху)
    try:
        # повторно используем логику /start
        await send_welcome(message)
    except Exception:
        # fallback: хотя бы обновить главное меню
        menu = get_menu(DEFAULT_MENU)
        kb = build_main_keyboard_from_menu(menu, is_admin_view_enabled(username, user_id))
        await message.answer(MENU_MESSAGES["main"], reply_markup=kb)


@dp.message(Command(commands=['refreshcommands','synccommands','sync']))
async def refresh_commands(message: Message):
    username = (message.from_user.username or '').lstrip('@').lower()
    if not _user_is_admin(username, message.from_user.id):
        return
    await _set_static_commands()
    await message.answer('✅ Команды обновлены! Список:\n/start - Главное меню\n/portfolio - Портфолио\n/services - Услуги и цены\n/booking - Онлайн-запись\n/promotions - Акции\n/reviews - Отзывы\n/social - Соцсети\n/adminmode - Админ режим')


@dp.message(Command(commands=['start']))
async def send_welcome(message: Message):
    username = (message.from_user.username or "").lstrip("@").lower()
    user_id = message.from_user.id
    
    # Save user to database for broadcast functionality
    add_user(
        user_id=user_id, 
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    is_admin = is_admin_view_enabled(username, user_id)
    # load menu from DB (default menu if none)
    menu = get_menu(DEFAULT_MENU)
    keyboard = build_main_keyboard_from_menu(menu, is_admin)
    keyboard = _inject_booking_status_button(keyboard, user_id)
    await _set_static_commands()

    # Отправляем фото приветствия с меню в одном сообщении
    image_file_id = get_setting('welcome_image_file_id', None)
    
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


def get_portfolio_keyboard_with_likes(slug: str, idx: int, user_id: int) -> InlineKeyboardMarkup:
    """Get portfolio photo keyboard with like information."""
    likes_count = get_photo_likes_count(slug, idx)
    user_has_liked = user_has_liked_photo(slug, idx, user_id)
    return build_category_photo_nav_keyboard(slug, idx, user_id, likes_count, user_has_liked)

# Command handlers for menu items
@dp.message(Command(commands=['portfolio']))
async def cmd_portfolio(message: Message):
    """Handle /portfolio command"""
    username = (message.from_user.username or "").lstrip("@").lower()
    cats = get_portfolio_categories()
    is_admin = is_admin_view_enabled(username, message.from_user.id)
    kb = build_portfolio_keyboard(cats, is_admin=is_admin)
    await message.answer(MENU_MESSAGES["portfolio"], reply_markup=kb)

@dp.message(Command(commands=['services']))
async def cmd_services(message: Message):
    """Handle /services command"""
    kb = build_services_keyboard()
    await message.answer(MENU_MESSAGES["services"], reply_markup=kb)

@dp.message(Command(commands=['booking']))
async def cmd_booking(message: Message):
    """Handle /booking command"""
    from datetime import datetime, timedelta, timezone
    BOOK_TZ = timezone.utc
    
    # Check if user already has a booking
    user_id = message.from_user.id
    bk = get_active_booking_for_user(user_id)
    if bk:
        dt = datetime.fromisoformat(bk['start_ts'])
        txt = (f'📅 Ваша запись:\n'
               f'Время: {dt.strftime("%H:%M %d.%m.%Y")}\n'
               f'Категория: {bk.get("category") or "—"}')
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Перенести', callback_data=f'bk_resch:{bk["id"]}')],
            [InlineKeyboardButton(text='Отменить', callback_data=f'bk_cancel_booking:{bk["id"]}')],
            [InlineKeyboardButton(text='⬅️ В меню', callback_data='back_main')]
        ])
        await message.answer(txt, reply_markup=kb)
        return
    
    # Start booking process
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📅 Записаться', callback_data='booking')],
        [InlineKeyboardButton(text='⬅️ В меню', callback_data='back_main')]
    ])
    await message.answer("📅 Онлайн-запись на фотосессию", reply_markup=kb)

@dp.message(Command(commands=['promotions']))
async def cmd_promotions(message: Message):
    """Handle /promotions command"""
    username = (message.from_user.username or "").lstrip("@").lower()
    
    # Cleanup expired promotions first
    cleanup_expired_promotions()
    
    # Get active promotions
    promotions = get_active_promotions()
    is_admin = is_admin_view_enabled(username, message.from_user.id)
    
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

@dp.message(Command(commands=['reviews']))
async def cmd_reviews(message: Message):
    """Handle /reviews command"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_main")]
    ])
    await message.answer("⭐ Отзывы клиентов:\n\nВ данный момент раздел находится в разработке.", reply_markup=kb)

@dp.message(Command(commands=['social']))
async def cmd_social(message: Message):
    """Handle /social command"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_main")]
    ])
    await message.answer("📱 Социальные сети:\n\nВ данный момент раздел находится в разработке.", reply_markup=kb)


@dp.callback_query()
async def handle_callback(query: CallbackQuery):
    # Fix for UnboundLocalError: explicitly declare imported classes as global
    global InlineKeyboardMarkup, InlineKeyboardButton
    
    data_raw = query.data or ""
    data = data_raw.lower()
    username = (query.from_user.username or "").lstrip("@").lower()

    # quick debug log to capture what callback data arrives from the client
    logging.info("HANDLER VERSION vDel2 | user=%s raw=%s lowered=%s", username, data_raw, data)

    try:
        await query.answer()
    except Exception:
        pass

    # public actions
    if data == "portfolio":
        cats = get_portfolio_categories()
        is_admin = is_admin_view_enabled(username, query.from_user.id)
        kb = build_portfolio_keyboard(cats, is_admin=is_admin)
        await query.message.answer(MENU_MESSAGES["portfolio"], reply_markup=kb)
        return
    if data == "services":
        kb = build_services_keyboard()
        await query.message.answer(MENU_MESSAGES["services"], reply_markup=kb)
        return
    
    if data == "promotions":
        # Cleanup expired promotions first
        cleanup_expired_promotions()
        
        # Get active promotions
        promotions = get_active_promotions()
        is_admin = is_admin_view_enabled(username, query.from_user.id)
        
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
        is_admin = is_admin_view_enabled(username, query.from_user.id)
        
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
        menu = get_menu(DEFAULT_MENU)
        is_admin = is_admin_view_enabled(username, query.from_user.id)
        keyboard = build_main_keyboard_from_menu(menu, is_admin)
        keyboard = _inject_booking_status_button(keyboard, query.from_user.id)
        await query.message.answer(MENU_MESSAGES["main"], reply_markup=keyboard)
        return
    
    # booking flow handled later (remove early stub)
    if data == "reviews":
        # Get reviews photos from database
        raw = get_setting('reviews_photos', '[]')
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
        
        if photos:
            # Sequential display: newest to oldest
            chat_key = (query.message.chat.id, 'reviews')
            last_idx = LAST_CATEGORY_PHOTO.get(chat_key)
            
            if last_idx is None:
                # First time, start from newest
                idx = len(photos) - 1
            else:
                # Navigate to previous (older) review
                idx = last_idx - 1
                if idx < 0:
                    # Reached oldest, cycle back to newest
                    idx = len(photos) - 1
                    
            fid = photos[idx]
            caption = f'⭐ Отзыв {idx+1} из {len(photos)}'
            try:
                await bot.send_photo(chat_id=query.message.chat.id, photo=fid, caption=caption, reply_markup=build_reviews_nav_keyboard(idx))
                LAST_CATEGORY_PHOTO[chat_key] = idx
            except Exception:
                await query.message.answer(f'⭐ Отзывы (ошибка отправки фото)', reply_markup=build_reviews_nav_keyboard(0))
        else:
            await query.message.answer('⭐ Отзывы пока не добавлены.')
        
        # Show admin controls for admins
        is_admin = is_admin_view_enabled(username, query.from_user.id)
        if is_admin:
            kb = build_reviews_admin_keyboard()
            await query.message.answer('Управление отзывами:', reply_markup=kb)
        return
    if data == "social":
        # Get social media text from database
        default_social_text = """Привет! Я Мария — фотограф и ретушёр 📸✨
Подписывайтесь на мои соцсети, чтобы видеть свежие съёмки, портфолио и реальные "до/после" ретуши, а также быстро написать мне в личные сообщения.

VK → https://vk.com/versavija

Instagram → https://www.instagram.com/versavija?igsh=Y3ZhdnFvbWN0ejlq

TikTok → https://www.tiktok.com/@00013_mariat_versavija?_t=ZS-8zC3OvSXSIZ&_r=1

Жду ваши вопросы в директ — отвечаю лично 💬"""
        
        social_text = get_setting('social_media_text', default_social_text)
        await query.message.answer(social_text)
        
        # Show edit button for admins
        is_admin = is_admin_view_enabled(username, query.from_user.id)
        if is_admin:
            kb = build_social_admin_keyboard()
            await query.message.answer('Управление соцсетями:', reply_markup=kb)
        return

    # portfolio category selection
    if data.startswith('pf:'):
        slug = data.split(':',1)[1]
        cats = get_portfolio_categories()
        cat = next((c for c in cats if c.get('slug') == slug), None)
        if not cat:
            await query.message.answer('Категория не найдена.')
            return
        # load stored file_ids list for this category
        key = f'portfolio_{slug}'
        raw = get_setting(key, '[]')
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
        
        photo_sent = False
        if photos:
            # Show photos from newest (last uploaded) to oldest
            cycle_key = (query.message.chat.id, slug)
            last_shown = LAST_CATEGORY_PHOTO.get((query.message.chat.id, slug), len(photos))  # Start from newest
            
            # Find next photo to show (going backwards from newest to oldest)
            if last_shown >= len(photos):
                # First time or reached beginning, start from newest
                idx = len(photos) - 1
            else:
                # Show previous photo (older)
                idx = last_shown - 1
                if idx < 0:
                    # Reached oldest, cycle back to newest
                    idx = len(photos) - 1
            
            fid = photos[idx]
            caption = f'📸 {cat.get("text")}'
            try:
                keyboard = get_portfolio_keyboard_with_likes(slug, idx, query.from_user.id)
                await bot.send_photo(chat_id=query.message.chat.id, photo=fid, caption=caption, reply_markup=keyboard)
                LAST_CATEGORY_PHOTO[(query.message.chat.id, slug)] = idx
                photo_sent = True
            except Exception:
                keyboard = get_portfolio_keyboard_with_likes(slug, 0, query.from_user.id)
                await query.message.answer(f'📸 {cat.get("text")} (ошибка отправки фото)', reply_markup=keyboard)
                photo_sent = True
        else:
            await query.message.answer(f'📸 Категория: {cat.get("text")} (нет фото)')
        
        is_admin = is_admin_view_enabled(username, query.from_user.id)
        if is_admin:
            kb = build_category_admin_keyboard(slug, has_photos=bool(photos))
            await query.message.answer('Управление категорией:', reply_markup=kb)
        else:
            if not photo_sent:
                kb = build_portfolio_keyboard(get_portfolio_categories(), page=0, is_admin=False)
                await query.message.answer('Категории:', reply_markup=kb)
        return

    # random photo navigation inside category
    if data.startswith('pf_pic:'):
        parts = data.split(':')
        if len(parts) < 3:
            return
        slug = parts[1]
        key = f'portfolio_{slug}'
        raw = get_setting(key, '[]')
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
        
        if photos:
            # Sequential navigation: newest to oldest, then cycle
            chat_key = (query.message.chat.id, slug)
            last_idx = LAST_CATEGORY_PHOTO.get(chat_key)
            
            if last_idx is None:
                # First time, start from newest
                idx = len(photos) - 1
            else:
                # Navigate to previous (older) photo
                idx = last_idx - 1
                if idx < 0:
                    # Reached oldest, cycle back to newest
                    idx = len(photos) - 1
                    
            fid = photos[idx]
            # resolve category display text
            cat_text = next((c.get('text') for c in get_portfolio_categories() if c.get('slug') == slug), slug)
            from aiogram.types import InputMediaPhoto
            try:
                logging.info("Attempting to edit_media for photo navigation: slug=%s, idx=%s", slug, idx)
                await query.message.edit_media(InputMediaPhoto(media=fid, caption=f'📸 {cat_text}'))
                keyboard = get_portfolio_keyboard_with_likes(slug, idx, query.from_user.id)
                await query.message.edit_reply_markup(reply_markup=keyboard)
                logging.info("Successfully edited media for photo navigation")
                LAST_CATEGORY_PHOTO[chat_key] = idx
            except Exception as e:
                # fallback new message
                logging.warning("Failed to edit_media, falling back to new message: %s", e)
                keyboard = get_portfolio_keyboard_with_likes(slug, idx, query.from_user.id)
                await bot.send_photo(chat_id=query.message.chat.id, photo=fid, caption=f'📸 {cat_text}', reply_markup=keyboard)
                LAST_CATEGORY_PHOTO[chat_key] = idx
        else:
            await query.message.answer('Нет фото в категории.')
        return

    # Photo like handler
    if data.startswith('like:'):
        parts = data.split(':')
        if len(parts) < 3:
            await query.answer("❌ Ошибка: неверный формат лайка")
            return
        
        slug = parts[1]
        try:
            photo_idx = int(parts[2])
        except ValueError:
            await query.answer("❌ Ошибка: неверный индекс фото")
            return
        
        user_id = query.from_user.id
        
        # Toggle like
        liked = toggle_photo_like(slug, photo_idx, user_id)
        
        # Get updated counts and status
        likes_count = get_photo_likes_count(slug, photo_idx)
        user_has_liked = user_has_liked_photo(slug, photo_idx, user_id)
        
        # Update keyboard with new like info
        try:
            keyboard = build_category_photo_nav_keyboard(slug, photo_idx, user_id, likes_count, user_has_liked)
            await query.message.edit_reply_markup(reply_markup=keyboard)
            
            # Show feedback
            if liked:
                await query.answer("❤️ Лайк поставлен!")
            else:
                await query.answer("💔 Лайк убран")
        except Exception as e:
            logging.warning(f"Failed to update like button: {e}")
            await query.answer("❤️ Лайк обновлен!")
        return

    # category admin back from delete list
    if data.startswith('pf_back_cat:'):
        slug = data.split(':',1)[1]
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        raw = get_setting(f'portfolio_{slug}', '[]')
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
        kb = build_category_admin_keyboard(slug, has_photos=bool(photos))
        await query.message.answer('Управление категорией:', reply_markup=kb)
        return

    # add photo flow start
    if data.startswith('pf_add:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        slug = data.split(':',1)[1]
        ADMIN_PENDING_ACTIONS[username] = {'action': 'add_photo_cat', 'payload': {'slug': slug}}
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await query.message.answer('Пришлите фото одним сообщением (из галереи).')
        return

    # delete all photos confirmation
    if data.startswith('pf_del_all_confirm:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        slug = data.split(':',1)[1]
        raw = get_setting(f'portfolio_{slug}', '[]')
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
        if not photos:
            await query.message.answer('Нет фото для очистки.')
            return
        await query.message.answer(f'Очистить ВСЕ фото ({len(photos)}) в категории? Это можно будет отменить.', reply_markup=build_confirm_delete_all_photos_kb(slug))
        return

    if data.startswith('pf_del_all_yes:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        slug = data.split(':',1)[1]
        raw = get_setting(f'portfolio_{slug}', '[]')
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
        if not photos:
            await query.message.answer('Категория уже пуста.')
            return
        # store for undo
        UNDO_DELETED_CATEGORY_PHOTOS[slug] = photos.copy()
        set_setting(f'portfolio_{slug}', json.dumps([], ensure_ascii=False))
        await query.message.answer(f'✅ Все фото ({len(photos)}) удалены.', reply_markup=build_undo_photo_delete_kb(slug))
        # show empty category admin panel again
        kb = build_category_admin_keyboard(slug, has_photos=False)
        await query.message.answer('Управление категорией:', reply_markup=kb)
        return

    if data.startswith('pf_del_all_no:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        slug = data.split(':',1)[1]
        await query.message.answer('Отменено.')
        # show admin panel again (photos still exist)
        raw = get_setting(f'portfolio_{slug}', '[]')
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
        kb = build_category_admin_keyboard(slug, has_photos=bool(photos))
        await query.message.answer('Управление категорией:', reply_markup=kb)
        return

    if data == 'noop':
        try:
            await query.answer()
        except Exception:
            pass
        return

    # delete photo choose
    if data.startswith('pf_del:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        slug = data.split(':',1)[1]
        raw = get_setting(f'portfolio_{slug}', '[]')
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
        if not photos:
            await query.message.answer('Нет фото для удаления.')
            return
        # Вместо списка номеров сразу показываем первое фото в режиме удаления
        try:
            fid = photos[0]
            from aiogram.types import FSInputFile, InputMediaPhoto
            await bot.send_photo(chat_id=query.message.chat.id, photo=fid, caption='🗑 Режим удаления', reply_markup=build_category_delete_viewer_keyboard(slug, 0))
        except Exception:
            # fallback на старый список при ошибке
            kb = build_category_delete_keyboard(slug, photos)
            await query.message.answer(MENU_MESSAGES["delete_photo"], reply_markup=kb)
        return

    if data.startswith('pf_del_idx:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        # format pf_del_idx:slug:idx
        parts = data.split(':')
        if len(parts) < 3:
            return
        slug = parts[1]
        try:
            del_idx = int(parts[2])
        except Exception:
            return
        key = f'portfolio_{slug}'
        raw = get_setting(key, '[]')
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
        if 0 <= del_idx < len(photos):
            removed = photos.pop(del_idx)
            set_setting(key, json.dumps(photos, ensure_ascii=False))
            await query.message.answer(f'🗑 Фото удалено (#{del_idx+1}).')
        else:
            await query.message.answer('Неверный индекс фото.')
        kb = build_category_admin_keyboard(slug, has_photos=bool(photos))
        await query.message.answer('Управление категорией:', reply_markup=kb)
        return

    # new deletion navigation
    if data.startswith('pf_delnav:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            return
        parts = data.split(':')
        if len(parts) < 3:
            return
        slug = parts[1]
        cur_idx = int(parts[2]) if parts[2].isdigit() else 0
        raw = get_setting(f'portfolio_{slug}', '[]')
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
        if not photos:
            await query.message.answer('Нет фото.')
            return
        import random
        # choose a different index if >1 photo
        if len(photos) > 1:
            candidates = [i for i in range(len(photos)) if i != cur_idx]
            if not candidates:
                candidates = list(range(len(photos)))
            new_idx = random.choice(candidates)
        else:
            new_idx = 0
        fid = photos[new_idx]
        from aiogram.types import InputMediaPhoto
        try:
            await query.message.edit_media(InputMediaPhoto(media=fid, caption='🗑 Режим удаления'))
            await query.message.edit_reply_markup(reply_markup=build_category_delete_viewer_keyboard(slug, new_idx))
        except Exception:
            await bot.send_photo(chat_id=query.message.chat.id, photo=fid, caption='🗑 Режим удаления', reply_markup=build_category_delete_viewer_keyboard(slug, new_idx))
        return

    if data.startswith('pf_delcurr:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            return
        parts = data.split(':')
        if len(parts) < 3:
            return
        slug = parts[1]
        del_idx = int(parts[2]) if parts[2].isdigit() else 0
        key = f'portfolio_{slug}'
        raw = get_setting(key, '[]')
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
        if 0 <= del_idx < len(photos):
            removed = photos.pop(del_idx)
            UNDO_DELETED_PHOTO[slug] = removed
            set_setting(key, json.dumps(photos, ensure_ascii=False))
            # adjust index
            next_idx = 0 if not photos else min(del_idx, len(photos)-1)
            if photos:
                fid = photos[next_idx]
                from aiogram.types import InputMediaPhoto
                try:
                    # Use edit_media with media and reply_markup in one call
                    await query.message.edit_media(
                        InputMediaPhoto(media=fid, caption='🗑 Удалено. Следующее.'),
                        reply_markup=build_category_delete_viewer_keyboard(slug, next_idx)
                    )
                except Exception:
                    await bot.send_photo(chat_id=query.message.chat.id, photo=fid, caption='🗑 Удалено. Следующее.', reply_markup=build_category_delete_viewer_keyboard(slug, next_idx))
                await query.message.answer('Фото удалено. Можно восстановить последнее.', reply_markup=build_undo_photo_delete_kb(slug))
            else:
                await query.message.answer('Все фото удалены.')
                kb = build_category_admin_keyboard(slug, has_photos=False)
                await query.message.answer('Управление категорией:', reply_markup=kb)
                return
        else:
            await query.message.answer('Индекс вне диапазона.')
        return

    if data.startswith('pf_del_done:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            return
        slug = data.split(':',1)[1]
        raw = get_setting(f'portfolio_{slug}', '[]')
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
        kb = build_category_admin_keyboard(slug, has_photos=bool(photos))
        await query.message.answer('Управление категорией:', reply_markup=kb)
        return

    # removed import local images function

    if data.startswith('pf_page:'):
        # pf_page:noop (ignore) or pf_page:<num>
        part = data.split(':',1)[1]
        if part == 'noop':
            return  # ignore center label
        try:
            page = int(part)
        except Exception:
            page = 0
        cats = get_portfolio_categories()
        is_admin = is_admin_view_enabled(username, query.from_user.id)
        kb = build_portfolio_keyboard(cats, page=page, is_admin=is_admin)
        # Edit only keyboard (keep original text)
        try:
            await query.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            # fallback: send new message if edit fails (e.g., message too old)
            await query.message.answer(MENU_MESSAGES["portfolio"], reply_markup=kb)
        return

    # Social media edit
    if data == 'social_edit':
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        ADMIN_PENDING_ACTIONS[username] = {'action': 'edit_social_text', 'payload': {}}
        await query.message.answer('📝 Отправьте новый текст для соцсетей:')
        return

    # Reviews navigation
    if data.startswith('reviews_pic:'):
        parts = data.split(':')
        if len(parts) >= 2:
            raw = get_setting('reviews_photos', '[]')
            try:
                photos = json.loads(raw)
                if not isinstance(photos, list):
                    photos = []
            except Exception:
                photos = []
            
            if photos:
                # Sequential navigation: newest to oldest, then cycle
                chat_key = (query.message.chat.id, 'reviews')
                last_idx = LAST_CATEGORY_PHOTO.get(chat_key)
                
                if last_idx is None:
                    # First time, start from newest
                    idx = len(photos) - 1
                else:
                    # Navigate to previous (older) review
                    idx = last_idx - 1
                    if idx < 0:
                        # Reached oldest, cycle back to newest
                        idx = len(photos) - 1
                        
                fid = photos[idx]
                caption = f'⭐ Отзыв {idx+1} из {len(photos)}'
                from aiogram.types import InputMediaPhoto
                try:
                    await query.message.edit_media(InputMediaPhoto(media=fid, caption=caption))
                    await query.message.edit_reply_markup(reply_markup=build_reviews_nav_keyboard(idx))
                    LAST_CATEGORY_PHOTO[chat_key] = idx
                except Exception:
                    # fallback new message
                    await bot.send_photo(chat_id=query.message.chat.id, photo=fid, caption=caption, reply_markup=build_reviews_nav_keyboard(idx))
                    LAST_CATEGORY_PHOTO[chat_key] = idx
        return

    # Reviews admin - add review
    if data == 'reviews_add':
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        ADMIN_PENDING_ACTIONS[username] = {'action': 'add_review', 'payload': {}}
        await query.message.answer('📝 Отправьте фотографию отзыва:')
        return

    # Reviews admin - delete review
    if data == 'reviews_del':
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        raw = get_setting('reviews_photos', '[]')
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
        
        if not photos:
            await query.message.answer('Нет отзывов для удаления.')
            return
        
        kb = build_reviews_delete_keyboard(photos)
        await query.message.answer(f'{MENU_MESSAGES["delete_review"]} (всего: {len(photos)}):', reply_markup=kb)
        return

    # Reviews delete specific review
    if data.startswith('reviews_del_idx:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        parts = data.split(':')
        if len(parts) >= 2:
            try:
                idx = int(parts[1])
                raw = get_setting('reviews_photos', '[]')
                photos = json.loads(raw)
                if 0 <= idx < len(photos):
                    deleted_id = photos.pop(idx)
                    set_setting('reviews_photos', json.dumps(photos, ensure_ascii=False))
                    await query.message.answer(f'✅ Отзыв #{idx+1} удален. Осталось: {len(photos)}')
                else:
                    await query.message.answer('Неверный индекс отзыва.')
            except (ValueError, json.JSONDecodeError):
                await query.message.answer('Ошибка при удалении отзыва.')
        return

    if data == 'back_main':
        # rebuild main keyboard
        menu = get_menu(DEFAULT_MENU)
        is_admin = is_admin_view_enabled(username, query.from_user.id)
        kb = build_main_keyboard_from_menu(menu, is_admin)
        kb = _inject_booking_status_button(kb, query.from_user.id)
        await query.message.answer(MENU_MESSAGES["main"], reply_markup=kb)
        return

    # Booking status button (only for special users)
    if data == 'booking_status':
        bk = get_active_booking_for_user(query.from_user.id)
        if not bk:
            # refresh menu (maybe was cancelled)
            menu = get_menu(DEFAULT_MENU)
            kb = build_main_keyboard_from_menu(menu, is_admin_view_enabled(username, query.from_user.id))
            kb = _inject_booking_status_button(kb, query.from_user.id)
            await query.message.answer(MENU_MESSAGES["main"], reply_markup=kb)
            return
        from datetime import datetime
        dt = datetime.fromisoformat(bk['start_ts'])
        txt = (f'📅 Ваша запись:\n'
               f'Время: {dt.strftime("%H:%M %d.%m.%Y")}\n'
               f'Категория: {bk.get("category") or "—"}')
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Перенести', callback_data=f'bk_resch:{bk["id"]}')],
            [InlineKeyboardButton(text='Отменить', callback_data=f'bk_cancel_booking:{bk["id"]}')],
            [InlineKeyboardButton(text='⬅️ В меню', callback_data='back_main')]
        ])
        await query.message.answer(txt, reply_markup=kb)
        return

    # (reschedule & cancel handlers moved below after booking helpers)

    # --- Booking flow ---
    from datetime import datetime, timedelta, timezone
    BOOK_TZ = timezone.utc
    async def _send_booking_step(q: CallbackQuery, text: str, kb: Optional[InlineKeyboardMarkup] = None):
        """Show next booking step using a single reusable message.

        Strategy:
        1. If current callback comes from the tracked booking step message -> edit it.
        2. Else (first step or tracking lost) delete any previously tracked booking messages and send a new one.
        3. Store only the current booking flow message id in BOOKING_FLOW_MSGS[chat].
        4. Caller may clear BOOKING_FLOW_MSGS afterwards (e.g. on cancel) to keep final text.
        """
        chat_id = q.message.chat.id
        tracked = BOOKING_FLOW_MSGS.get(chat_id, [])
        # Case 1: edit in place
        if tracked and q.message and q.message.message_id in tracked:
            old_text = q.message.text or ''
            animate = old_text != text  # only animate if content really changes
            try:
                if animate:
                    # evaporation animation: progressively replace chars with dots then shrink
                    import asyncio, random
                    dots = ['·','•','∙','⋅','∘','⁘','⁙','⁚','﹒']
                    # build 4 intermediate frames
                    length = len(old_text)
                    # frame 1: 30% chars replaced
                    # frame 2: 70% chars replaced
                    # frame 3: all dots
                    # frame 4: sparse dots
                    def replace_portion(src: str, portion: float):
                        if not src:
                            return ''
                        idxs = list(range(len(src)))
                        random.shuffle(idxs)
                        cut = int(len(src)*portion)
                        repl_set = set(idxs[:cut])
                        out = []
                        for i,ch in enumerate(src):
                            if ch == '\n':
                                out.append('\n'); continue
                            out.append(random.choice(dots) if i in repl_set and ch.strip() else ch)
                        return ''.join(out)
                    frames = [replace_portion(old_text, p) for p in (0.3,0.7)]
                    frames.append(''.join(random.choice(dots) if c.strip() else c for c in old_text))
                    sparse = ''.join(random.choice(dots) if random.random()<0.15 and c.strip() else (' ' if c!='\n' else '\n') for c in old_text)
                    frames.append(sparse)
                    for f in frames:
                        try:
                            await q.message.edit_text(f, reply_markup=None)
                        except Exception:
                            break
                        await asyncio.sleep(0.12)
                # final content
                await q.message.edit_text(text, reply_markup=kb)
                BOOKING_FLOW_MSGS[chat_id] = [q.message.message_id]
                return q.message
            except Exception:
                # If edit fails (older than 48h / content same / message changed), fallback to recreate
                pass
        # Case 2: delete old tracked messages then send fresh
        for mid in tracked:
            try:
                await bot.delete_message(chat_id, mid)
            except Exception:
                pass
        m = await bot.send_message(chat_id, text, reply_markup=kb)
        BOOKING_FLOW_MSGS[chat_id] = [m.message_id]
        return m
    def build_booking_date_kb():
        today = datetime.now(BOOK_TZ).date()
        # Начинаем с завтрашней даты (минимум +1 день от текущей)
        dates = [today + timedelta(days=i) for i in range(1, 31)]  # с 1 дня (завтра) на 30 дней вперед
        rows = []
        row = []
        for d in dates:
            row.append(InlineKeyboardButton(text=d.strftime('%d.%m'), callback_data=f'bk_d:{d.isoformat()}'))
            if len(row) == 5:
                rows.append(row); row = []
        if row: rows.append(row)
        rows.append([InlineKeyboardButton(text='❌ Отмена', callback_data='bk_cancel')])
        return InlineKeyboardMarkup(inline_keyboard=rows)
    def build_booking_hours_kb(date_iso: str):
        from db import get_bookings_between
        start = datetime.fromisoformat(date_iso).replace(tzinfo=BOOK_TZ)
        end = start + timedelta(days=1)
        # Base taken hours: booked start hours plus their reserved buffer hour (start+1)
        booking_hours = [datetime.fromisoformat(b['start_ts']).hour for b in get_bookings_between(start.isoformat(), end.isoformat())]
        taken = set()
        for h in booking_hours:
            taken.add(h)
            if h + 1 < 24:  # buffer hour
                taken.add(h + 1)
        # Business rule:
        #  * Weekdays (Mon-Fri, weekday 0-4): slots 18:00..21:00
        #  * Weekends (Sat-Sun, weekday 5-6): slots 10:00..21:00
        if start.weekday() < 5:  # Mon-Fri
            hours = list(range(18, 22))
        else:  # Sat/Sun
            hours = list(range(10, 22))
        rows = []
        row = []
        for h in hours:
            busy = h in taken
            cb = 'bk_h_taken' if busy else f'bk_h:{date_iso}:{h}'
            row.append(InlineKeyboardButton(text=f'{h:02d}:00'+(' ⛔' if busy else ''), callback_data=cb))
            if len(row)==3:
                rows.append(row); row=[]
        if row: rows.append(row)
        rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data='bk_back_date')])
        rows.append([InlineKeyboardButton(text='❌ Отмена', callback_data='bk_cancel')])
        return InlineKeyboardMarkup(inline_keyboard=rows)
    def build_booking_confirm_kb(date_iso: str, hour: int):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✅ Подтвердить', callback_data=f'bk_cf:{date_iso}:{hour}')],
            [InlineKeyboardButton(text='↩️ Изменить', callback_data='bk_back_date')],
            [InlineKeyboardButton(text='❌ Отмена', callback_data='bk_cancel')]
        ])

    # Booking flow callbacks
    if data == 'booking':
        # Prevent second active future booking (unless coming from explicit reschedule button)
        existing = get_active_booking_for_user(query.from_user.id)
        if existing:
            from datetime import datetime as _dt, timezone as _tz
            try:
                dt_ex = _dt.fromisoformat(existing['start_ts'])
            except Exception:
                dt_ex = None
            if dt_ex and dt_ex > _dt.now(_tz.utc):
                # Show status card instead of starting new flow
                txt = (f'У вас уже есть активная запись:\n'
                       f'{dt_ex.strftime("%H:%M %d.%m.%Y")} – {existing.get("category") or "(категория)"}')
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text='Перенести', callback_data=f'bk_resch:{existing["id"]}')],
                    [InlineKeyboardButton(text='Отменить', callback_data=f'bk_cancel_booking:{existing["id"]}')],
                    [InlineKeyboardButton(text='⬅️ В меню', callback_data='back_main')]
                ])
                await query.message.answer(txt, reply_markup=kb)
                return
        set_setting(f'resched_{query.from_user.id}', '')  # clear reschedule flag if starting fresh
        BOOKING_FLOW_MSGS[query.message.chat.id] = []
        await _send_booking_step(query, 'Выберите дату:', build_booking_date_kb())
        return
    if data == 'bk_cancel':
        await _send_booking_step(query, 'Запись отменена.')
        BOOKING_FLOW_MSGS[query.message.chat.id] = []
        set_setting(f'pending_booking_{query.from_user.id}', '')
        return
    if data == 'bk_back_date':
        await _send_booking_step(query, 'Выберите дату:', build_booking_date_kb())
        return
    if data.startswith('bk_d:'):
        date_iso = data.split(':',1)[1]
        await _send_booking_step(query, f'Дата {datetime.fromisoformat(date_iso).strftime("%d.%m.%Y")}. Выберите время:', build_booking_hours_kb(date_iso))
        return
    if data == 'bk_h_taken':
        await query.answer('Занято')
        return
    if data.startswith('bk_h:'):
        _, date_iso, hour = data.split(':',2)
        hour = int(hour)
        start_dt = datetime.fromisoformat(date_iso).replace(tzinfo=BOOK_TZ,hour=hour,minute=0,second=0,microsecond=0)
        buffer_dt = start_dt + timedelta(hours=1)
        prev_dt = start_dt - timedelta(hours=1)
        if is_slot_taken(start_dt.isoformat()) or is_slot_taken(buffer_dt.isoformat()) or is_slot_taken(prev_dt.isoformat()):
            await query.answer('Слот занят')
            return
        cats = get_portfolio_categories()
        rows = []; row=[]
        for c in cats:
            row.append(InlineKeyboardButton(text=c.get('text'), callback_data=f'bk_cat:{date_iso}:{hour}:{c.get("slug")}'))
            if len(row)==2:
                rows.append(row); row=[]
        if row: rows.append(row)
        rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data='bk_back_date')])
        rows.append([InlineKeyboardButton(text='❌ Отмена', callback_data='bk_cancel')])
        await _send_booking_step(query, MENU_MESSAGES["booking"], InlineKeyboardMarkup(inline_keyboard=rows))
        return
    if data.startswith('bk_cat:'):
        _, date_iso, hour, slug = data.split(':',3)
        hour = int(hour)
        start_dt = datetime.fromisoformat(date_iso).replace(tzinfo=BOOK_TZ,hour=hour,minute=0,second=0,microsecond=0)
        buffer_dt = start_dt + timedelta(hours=1)
        prev_dt = start_dt - timedelta(hours=1)
        if is_slot_taken(start_dt.isoformat()) or is_slot_taken(buffer_dt.isoformat()) or is_slot_taken(prev_dt.isoformat()):
            await query.answer('Слот занят')
            return
        set_setting(f'pending_booking_{query.from_user.id}', json.dumps({'date': date_iso, 'hour': hour, 'slug': slug}, ensure_ascii=False))
        cat = next((c for c in get_portfolio_categories() if c.get('slug')==slug), {'text': slug})
        human = start_dt.strftime('%d.%m.%Y %H:%M')
        await _send_booking_step(query, f'Вы выбрали {human}\nКатегория: {cat.get("text")}\nПодтвердить?', build_booking_confirm_kb(date_iso, hour))
        return
    if data.startswith('bk_cf:'):
        _, date_iso, hour = data.split(':',2)
        hour = int(hour)
        start_dt = datetime.fromisoformat(date_iso).replace(tzinfo=BOOK_TZ,hour=hour,minute=0,second=0,microsecond=0)
        buffer_dt = start_dt + timedelta(hours=1)
        prev_dt = start_dt - timedelta(hours=1)
        if is_slot_taken(start_dt.isoformat()) or is_slot_taken(buffer_dt.isoformat()) or is_slot_taken(prev_dt.isoformat()):
            await query.message.answer('Слот уже занят, начните заново.')
            return
        pending_raw = get_setting(f'pending_booking_{query.from_user.id}', None)
        slug = None
        if pending_raw:
            try:
                slug = json.loads(pending_raw).get('slug')
            except Exception:
                slug = None
        if not slug:
            await query.message.answer('Категория утрачена, начните заново.')
            await query.message.answer(MENU_MESSAGES["select_date"], reply_markup=build_booking_date_kb())
            return
        cat = next((c for c in get_portfolio_categories() if c.get('slug')==slug), {'text': slug})
        # reschedule?
        res_raw = get_setting(f'resched_{query.from_user.id}', None)
        res_info = {}
        if res_raw:
            try:
                res_info = json.loads(res_raw)
            except Exception:
                res_info = {}
        if res_info.get('bid'):
            old_bk = get_booking(res_info['bid'])
            if old_bk and old_bk['user_id']==query.from_user.id and old_bk['status'] in ('active','confirmed'):
                old_start = old_bk['start_ts']
                update_booking_time_and_category(res_info['bid'], start_dt.isoformat(), cat.get('text'))
                await _send_booking_step(query, f'🔁 Запись обновлена: {start_dt.strftime("%d.%m.%Y %H:%M")}')
                from datetime import datetime as _dt
                old_h = _dt.fromisoformat(old_start).strftime('%H:%M %d.%m.%Y')
                new_h = start_dt.strftime('%H:%M %d.%m.%Y')
                for aid in _get_all_admin_ids():
                    try:
                        await bot.send_message(aid, f'🔁 Пользователь @{username or "(нет)"} перенёс запись: {old_h} -> {new_h}. Категория: "{cat.get("text")}"')
                    except Exception:
                        pass
                _add_booking_status_user(query.from_user.id)
            else:
                await query.message.answer('Исходная запись не найдена, создана новая.')
                bid = add_booking(query.from_user.id, username, query.message.chat.id, start_dt.isoformat(), cat.get('text'))
                _add_booking_status_user(query.from_user.id)
            set_setting(f'resched_{query.from_user.id}', '')
        else:
            bid = add_booking(query.from_user.id, username, query.message.chat.id, start_dt.isoformat(), cat.get('text'))
            await _send_booking_step(query, f'✅ Запись создана: {start_dt.strftime("%d.%m.%Y %H:%M")} (с резервом до {buffer_dt.strftime("%H:%M")}). Напоминание за 24 часа.')
            for aid in _get_all_admin_ids():
                try:
                    await bot.send_message(aid, f'🆕 Добавлена запись @{username or "(нет)"}: {start_dt.strftime("%H:%M %d.%m.%Y")} Категория: "{cat.get("text")}"')
                except Exception:
                    pass
            _add_booking_status_user(query.from_user.id)
        set_setting(f'pending_booking_{query.from_user.id}', '')
        # send updated main menu with status button
        menu = get_menu(DEFAULT_MENU)
        kb_main = build_main_keyboard_from_menu(menu, is_admin_view_enabled(username, query.from_user.id))
        kb_main = _inject_booking_status_button(kb_main, query.from_user.id)
        await bot.send_message(query.message.chat.id, MENU_MESSAGES["main"], reply_markup=kb_main)
        return

    # Reschedule (after helper defs)
    if data.startswith('bk_resch:'):
        try:
            bid = int(data.split(':',1)[1])
        except Exception:
            return
        bk = get_booking(bid)
        if not bk or bk['user_id'] != query.from_user.id or bk['status'] not in ('active','confirmed'):
            await query.message.answer('Невозможно перенести: запись не найдена.')
            return
        set_setting(f'resched_{query.from_user.id}', json.dumps({'bid': bid, 'old_start': bk['start_ts']}, ensure_ascii=False))
        BOOKING_FLOW_MSGS[query.message.chat.id] = []
        await _send_booking_step(query, 'Выберите дату:', build_booking_date_kb())
        return

    # Cancel existing booking
    if data.startswith('bk_cancel_booking:'):
        try:
            bid = int(data.split(':',1)[1])
        except Exception:
            return
        bk = get_booking(bid)
        if not bk or bk['user_id'] != query.from_user.id or bk['status'] not in ('active','confirmed'):
            await query.message.answer('Невозможно отменить: запись не найдена.')
            return
        update_booking_status(bid, 'cancelled')
        from datetime import datetime as _dt
        dt_old = None
        try:
            dt_old = _dt.fromisoformat(bk['start_ts']).strftime('%H:%M %d.%m.%Y')
        except Exception:
            dt_old = bk['start_ts']
        for aid in _get_all_admin_ids():
            try:
                await bot.send_message(aid, f'❌ Пользователь @{username or "(нет)"} отменил запись на {dt_old}.')
            except Exception:
                pass
        menu = get_menu(DEFAULT_MENU)
        kb = build_main_keyboard_from_menu(menu, is_admin_view_enabled(username, query.from_user.id))
        kb = _inject_booking_status_button(kb, query.from_user.id)
        await query.message.answer(MENU_MESSAGES["main"], reply_markup=kb)
        return

    # admin actions
    if data == 'admin':
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        kb = admin_panel_keyboard(is_admin_view_enabled(username, query.from_user.id))
        await query.message.answer(MENU_MESSAGES["admin"], reply_markup=kb)
        return

    # start new category creation
    if data == 'pf_cat_new':
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        ADMIN_PENDING_ACTIONS[username] = {'action': 'new_category', 'payload': {}}
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await query.message.answer('Введите название новой категории (текст кнопки).')
        return

    # rename category initiate
    if data.startswith('pf_cat_ren:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        slug = data.split(':',1)[1]
        cats = get_portfolio_categories()
        cat = next((c for c in cats if c.get('slug') == slug), None)
        if not cat:
            await query.message.answer('Категория не найдена.')
            return
        ADMIN_PENDING_ACTIONS[username] = {'action': 'rename_category', 'payload': {'slug': slug}}
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await query.message.answer(f"Введите новое название для категории '{cat.get('text')}'")
        return

    # delete category confirmation
    if data.startswith('pf_cat_del:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        slug = data.split(':',1)[1]
        cats = get_portfolio_categories()
        cat = next((c for c in cats if c.get('slug') == slug), None)
        if not cat:
            await query.message.answer('Категория не найдена.')
            return
        await query.message.answer(f"Подтвердите удаление категории '{cat.get('text')}' и всех её фото.", reply_markup=build_confirm_delete_category_kb(slug))
        return

    if data.startswith('pf_cat_del_yes:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer('🚫 Нет доступа.')
            return
        slug = data.split(':',1)[1]
        cats = get_portfolio_categories()
        cat = next((c for c in cats if c.get('slug') == slug), None)
        if not cat:
            await query.message.answer('Категория уже отсутствует.')
            return
        new_cats = [c for c in cats if c is not cat]
        raw_ph = get_setting(f'portfolio_{slug}', '[]')
        try:
            photos_backup = json.loads(raw_ph)
        except Exception:
            photos_backup = []
        UNDO_DELETED_CATEGORY[slug] = cat
        UNDO_DELETED_CATEGORY_PHOTOS[slug] = photos_backup
        set_setting('portfolio_categories', json.dumps(new_cats, ensure_ascii=False))
        set_setting(f'portfolio_{slug}', json.dumps([]))
        kb = build_portfolio_keyboard(new_cats, is_admin=True)
        await query.message.answer('Категория удалена. Можно отменить.', reply_markup=kb)
        await query.message.answer('↩️ Отменить удаление?', reply_markup=build_undo_category_delete_kb(slug))
        return

    if data.startswith('pf_cat_del_no:'):
        await query.message.answer('Удаление отменено.')
        return

    if data.startswith('pf_undo_cat:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            return
        slug = data.split(':',1)[1]
        cat = UNDO_DELETED_CATEGORY.pop(slug, None)
        photos_restore = UNDO_DELETED_CATEGORY_PHOTOS.pop(slug, None)
        if not cat:
            await query.message.answer('Нечего восстанавливать.')
            return
        cats = get_portfolio_categories()
        cats.append(cat)
        set_setting('portfolio_categories', json.dumps(cats, ensure_ascii=False))
        if photos_restore is not None:
            set_setting(f'portfolio_{slug}', json.dumps(photos_restore, ensure_ascii=False))
        kb = build_portfolio_keyboard(cats, is_admin=True)
        await query.message.answer('✅ Категория восстановлена.', reply_markup=kb)
        return

    if data.startswith('pf_undo_photo:'):
        if not is_admin_view_enabled(username, query.from_user.id):
            return
        slug = data.split(':',1)[1]
        photo_id = UNDO_DELETED_PHOTO.pop(slug, None)
        if not photo_id:
            await query.message.answer('Нет фото для восстановления.')
            return
        key = f'portfolio_{slug}'
        raw = get_setting(key, '[]')
        try:
            photos = json.loads(raw)
            if not isinstance(photos, list):
                photos = []
        except Exception:
            photos = []
        if photo_id not in photos:
            photos.append(photo_id)
            set_setting(key, json.dumps(photos, ensure_ascii=False))
            await query.message.answer('✅ Фото восстановлено.')
        else:
            await query.message.answer('Фото уже существует в категории.')
        return

    if data == 'admin_broadcast':
        if username not in ADMIN_USERNAMES:
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        ADMIN_PENDING_ACTIONS[username] = {'action': 'broadcast_text'}
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await query.message.answer('📢 Отправьте текст сообщения для рассылки всем пользователям бота.')
        return

    if data == 'broadcast_confirm':
        if username not in ADMIN_USERNAMES:
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        # Get stored broadcast data
        broadcast_text = get_setting(f'broadcast_temp_text_{username}', '')
        broadcast_image = get_setting(f'broadcast_temp_image_{username}', '')
        if not broadcast_text:
            await query.message.answer('❌ Текст для рассылки не найден. Попробуйте снова.')
            return
        
        await perform_broadcast(broadcast_text, broadcast_image if broadcast_image else None, query.message)
        # Clear temporary data
        set_setting(f'broadcast_temp_text_{username}', '')
        set_setting(f'broadcast_temp_image_{username}', '')
        return

    if data == 'broadcast_cancel':
        if username not in ADMIN_USERNAMES:
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        # Clear temporary data
        set_setting(f'broadcast_temp_text_{username}', '')
        set_setting(f'broadcast_temp_image_{username}', '')
        await query.message.answer('❌ Рассылка отменена.')
        return

    if data == 'broadcast_no_image':
        if username not in ADMIN_USERNAMES:
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        # Skip image and go to confirmation
        broadcast_text = get_setting(f'broadcast_temp_text_{username}', '')
        if not broadcast_text:
            await query.message.answer('❌ Текст для рассылки не найден. Попробуйте снова.')
            return
        
        users = get_all_users()
        user_count = len(users)
        preview_text = broadcast_text[:200] + ("..." if len(broadcast_text) > 200 else "")
        
        await query.message.answer(
            f"📢 Готов к рассылке!\n\n"
            f"📝 Текст сообщения:\n{preview_text}\n\n"
            f"🖼️ Изображение: Без изображения\n\n"
            f"👥 Количество получателей: {user_count}\n\n"
            f"Подтвердите отправку:",
            reply_markup=build_broadcast_confirm_keyboard()
        )
        return

    if data == 'add_promotion':
        if username not in ADMIN_USERNAMES:
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        ADMIN_PENDING_ACTIONS[username] = {'action': 'add_promotion_title'}
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await query.message.answer('📝 Введите название акции:')
        return

    # Promotion "no image" handler
    if data == 'promo_no_image':
        if username not in ADMIN_USERNAMES:
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        
        # Get current pending action data
        pending = ADMIN_PENDING_ACTIONS.get(username, {})
        if pending.get('action') != 'add_promotion_image':
            await query.message.answer("❌ Ошибка: неожиданное состояние. Начните заново.")
            return
        
        payload = pending.get('payload', {})
        title = payload.get('title')
        description = payload.get('description')
        
        # Skip image, go to date selection
        ADMIN_PENDING_ACTIONS[username] = {
            'action': 'add_promotion_start_date', 
            'payload': {'title': title, 'description': description, 'image_file_id': None}
        }
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        
        from datetime import datetime
        await query.message.edit_text('✅ Акция будет создана без изображения\n\n📅 Выберите дату начала акции:', 
                             reply_markup=build_promotion_date_keyboard(datetime.now().year, datetime.now().month, 'promo_start_date'))
        return

    # Promotion date selection handlers
    if data.startswith('promo_start_date:'):
        if username not in ADMIN_USERNAMES:
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        
        # Extract selected date
        selected_date = data.split(':', 1)[1]  # Format: 2024-01-15
        
        # Get current pending action data
        pending = ADMIN_PENDING_ACTIONS.get(username, {})
        if pending.get('action') != 'add_promotion_start_date':
            await query.message.answer("❌ Ошибка: неожиданное состояние. Начните заново.")
            return
        
        payload = pending.get('payload', {})
        payload['start_date'] = selected_date
        
        # Ask for end date
        ADMIN_PENDING_ACTIONS[username] = {
            'action': 'add_promotion_end_date',
            'payload': payload
        }
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        
        from datetime import datetime
        await query.message.edit_text(f'✅ Дата начала выбрана: {selected_date}\n\n📅 Теперь выберите дату окончания акции:', 
                                      reply_markup=build_promotion_date_keyboard(datetime.now().year, datetime.now().month, 'promo_end_date'))
        return

    if data.startswith('promo_end_date:'):
        if username not in ADMIN_USERNAMES:
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        
        # Extract selected date
        selected_date = data.split(':', 1)[1]  # Format: 2024-01-15
        
        # Get current pending action data
        pending = ADMIN_PENDING_ACTIONS.get(username, {})
        if pending.get('action') != 'add_promotion_end_date':
            await query.message.answer("❌ Ошибка: неожиданное состояние. Начните заново.")
            return
        
        payload = pending.get('payload', {})
        start_date = payload.get('start_date')
        
        # Validate that end date is after start date
        from datetime import datetime
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(selected_date, '%Y-%m-%d')
            
            if end_dt <= start_dt:
                await query.message.answer("❌ Дата окончания должна быть позже даты начала. Выберите другую дату.")
                return
        except ValueError:
            await query.message.answer("❌ Ошибка формата даты. Попробуйте снова.")
            return
        
        # Create promotion
        title = payload.get('title')
        description = payload.get('description')
        image_file_id = payload.get('image_file_id')
        
        try:
            add_promotion(title, description, start_date, selected_date, str(query.from_user.id), image_file_id)
            ADMIN_PENDING_ACTIONS.pop(username, None)
            save_pending_actions(ADMIN_PENDING_ACTIONS)
            
            await query.message.edit_text(f'✅ Акция "{title}" успешно создана!\n\n📅 Период: {start_date} - {selected_date}')
        except Exception as e:
            await query.message.answer(f"❌ Ошибка при создании акции: {str(e)}")
        return

    # Calendar navigation handlers
    if data.startswith('promo_start_date_cal:') or data.startswith('promo_end_date_cal:'):
        if username not in ADMIN_USERNAMES:
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        
        # Extract action and date
        action_type = 'promo_start_date' if data.startswith('promo_start_date_cal:') else 'promo_end_date'
        date_part = data.split(':', 1)[1]  # Format: 2024-02
        
        try:
            year, month = map(int, date_part.split('-'))
            from datetime import datetime
            
            if action_type == 'promo_start_date':
                text = '📅 Выберите дату начала акции:'
            else:
                text = '📅 Выберите дату окончания акции:'
            
            await query.message.edit_text(text, 
                                          reply_markup=build_promotion_date_keyboard(year, month, action_type))
        except ValueError:
            await query.message.answer("❌ Ошибка формата даты.")
        return

    # Handle promotion deletion
    if data.startswith('delete_promotion:'):
        if username not in ADMIN_USERNAMES:
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        
        try:
            promotion_idx = int(data.split(':', 1)[1])
        except (ValueError, IndexError):
            await query.message.answer("❌ Ошибка: неверный индекс акции.")
            return
        
        # Get active promotions to find the actual promotion ID
        promotions = get_active_promotions()
        if not promotions or promotion_idx >= len(promotions):
            await query.message.answer("❌ Акция не найдена.")
            return
        
        promotion = promotions[promotion_idx]
        promo_id, title, description, image_file_id, start_date, end_date, created_by = promotion
        
        # Create confirmation keyboard
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_promotion:{promo_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="promotions")
            ]
        ])
        
        # Send new message instead of editing (original might be image-only)
        await query.message.answer(
            f"🗑️ **Подтверждение удаления**\n\n"
            f"Вы действительно хотите удалить акцию?\n\n"
            f"**{title}**\n\n"
            f"⚠️ Это действие нельзя отменить!",
            reply_markup=confirm_kb,
            parse_mode="Markdown"
        )
        return

    # Handle promotion deletion confirmation
    if data.startswith('confirm_delete_promotion:'):
        if username not in ADMIN_USERNAMES:
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        
        try:
            promo_id = int(data.split(':', 1)[1])
        except (ValueError, IndexError):
            await query.message.answer("❌ Ошибка: неверный ID акции.")
            return
        
        try:
            # Delete the promotion from database
            delete_promotion(promo_id)
            
            # Get updated promotions list
            promotions = get_active_promotions()
            
            if not promotions:
                # No more promotions left
                if is_admin_view_enabled(username, query.from_user.id):
                    kb = build_add_promotion_keyboard()
                    await query.message.edit_text(
                        "✅ Акция успешно удалена!\n\n"
                        "🎉 На текущий момент нет действующих акций. Мы работаем над этим! 😊", 
                        reply_markup=kb
                    )
                else:
                    await query.message.edit_text(
                        "✅ Акция успешно удалена!\n\n"
                        "🎉 На текущий момент нет действующих акций. Мы работаем над этим! 😊"
                    )
            else:
                # Show first remaining promotion
                await query.message.edit_text("✅ Акция успешно удалена!")
                await update_promotion_message(query, 0, promotions, is_admin_view_enabled(username, query.from_user.id))
        except Exception as e:
            await query.message.edit_text(f"❌ Ошибка при удалении акции: {str(e)}")
        return


async def perform_broadcast(text: str, image_file_id: str = None, message: Message = None):
    """Send broadcast message to all users."""
    users = get_all_users()
    sent = 0
    failed = 0
    
    broadcast_type = "с изображением" if image_file_id else "только текст"
    await message.answer(f"📤 Начинаю рассылку ({broadcast_type}) для {len(users)} пользователей...")
    
    for user_id, username, first_name, last_name in users:
        try:
            if image_file_id:
                await bot.send_photo(user_id, image_file_id, caption=text)
            else:
                await bot.send_message(user_id, text)
            sent += 1
        except Exception as e:
            failed += 1
            logging.warning(f"Failed to send broadcast to user {user_id}: {e}")
    
    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"📨 Отправлено: {sent}\n"
        f"❌ Не доставлено: {failed}\n"
        f"📊 Всего пользователей: {len(users)}"
    )


@dp.message()
async def handle_admin_pending(message: Message):
    username = (message.from_user.username or "").lstrip("@").lower()
    # allow only if admin mode ON (else ignore silently)
    if not is_admin_view_enabled(username, message.from_user.id):
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

    if a == 'broadcast_text':
        if not message.text:
            await message.answer('❌ Ожидаю текст для рассылки. Пожалуйста, отправьте текст сообщения.')
            return
        
        text = message.text.strip()
        if not text:
            await message.answer('❌ Текст не может быть пустым. Попробуйте снова.')
            return
        
        # Store broadcast text temporarily
        set_setting(f'broadcast_temp_text_{username}', text)
        
        # Move to image step
        ADMIN_PENDING_ACTIONS[username] = {'action': 'broadcast_image', 'payload': {'text': text}}
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        
        await message.answer(
            f'✅ Текст сохранён: "{text[:100]}{"..." if len(text) > 100 else ""}"\n\n'
            f'🖼️ Теперь пришлите изображение для рассылки или выберите "Без фото":',
            reply_markup=build_broadcast_image_keyboard()
        )
        return

    if a == 'broadcast_image':
        text = payload.get('text', '')
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
            await message.answer('❌ Ожидаю изображение. Используйте кнопку "Без фото" если хотите сделать рассылку без изображения.')
            return
        
        # Store image temporarily
        set_setting(f'broadcast_temp_image_{username}', image_file_id)
        
        # Clear pending action and show confirmation
        ADMIN_PENDING_ACTIONS.pop(username, None)
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        
        users = get_all_users()
        user_count = len(users)
        preview_text = text[:200] + ("..." if len(text) > 200 else "")
        
        await message.answer(
            f"📢 Готов к рассылке!\n\n"
            f"📝 Текст сообщения:\n{preview_text}\n\n"
            f"�️ Изображение: Прикреплено\n\n"
            f"�👥 Количество получателей: {user_count}\n\n"
            f"Подтвердите отправку:",
            reply_markup=build_broadcast_confirm_keyboard()
        )
        return

    # Process other admin actions
    a = action.get('action')
    payload = action.get('payload', {})
    if a == 'new_category':
            if not message.text:
                await message.answer('Ожидаю название категории. Попробуйте снова.')
                return
            title = message.text.strip()
            if not title:
                await message.answer('Название не может быть пустым.')
                ADMIN_PENDING_ACTIONS.pop(username, None)
                save_pending_actions(ADMIN_PENDING_ACTIONS)
                return
            from utils import normalize_callback
            slug = normalize_callback(title)
            cats = get_portfolio_categories()
            if any(c.get('slug') == slug for c in cats):
                await message.answer(f'Категория со slug "{slug}" уже существует. Измените название.')
                return
            cats.append({'text': title, 'slug': slug})
            set_setting('portfolio_categories', json.dumps(cats, ensure_ascii=False))
            folder = Path('media') / 'portfolio' / slug
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            ADMIN_PENDING_ACTIONS.pop(username, None)
            save_pending_actions(ADMIN_PENDING_ACTIONS)
            await message.answer(f'✅ Категория "{title}" создана.')
            kb = build_portfolio_keyboard(cats, is_admin=True)
            await message.answer('Обновлённый список категорий:', reply_markup=kb)
            return
    if a == 'rename_category':
            if not message.text:
                await message.answer('Ожидаю новое название. Попробуйте снова.')
                return
            new_title = message.text.strip()
            if not new_title:
                await message.answer('Название не может быть пустым.')
                ADMIN_PENDING_ACTIONS.pop(username, None)
                save_pending_actions(ADMIN_PENDING_ACTIONS)
                return
            slug = payload.get('slug')
            cats = get_portfolio_categories()
            cat = next((c for c in cats if c.get('slug') == slug), None)
            if not cat:
                await message.answer('Категория не найдена.')
                ADMIN_PENDING_ACTIONS.pop(username, None)
                save_pending_actions(ADMIN_PENDING_ACTIONS)
                return
            old_title = cat.get('text')
            cat['text'] = new_title
            set_setting('portfolio_categories', json.dumps(cats, ensure_ascii=False))
            ADMIN_PENDING_ACTIONS.pop(username, None)
            save_pending_actions(ADMIN_PENDING_ACTIONS)
            await message.answer(f'✅ Категория "{old_title}" переименована в "{new_title}".')
            kb = build_portfolio_keyboard(cats, is_admin=True)
            await message.answer('Обновлённый список категорий:', reply_markup=kb)
            return
        
    if a == 'edit_social_text':
            if not message.text:
                await message.answer('Ожидаю текст для соцсетей. Попробуйте снова.')
                return
            new_text = message.text.strip()
            if not new_text:
                await message.answer('Текст не может быть пустым.')
                ADMIN_PENDING_ACTIONS.pop(username, None)
                save_pending_actions(ADMIN_PENDING_ACTIONS)
                return
            set_setting('social_media_text', new_text)
            ADMIN_PENDING_ACTIONS.pop(username, None)
            save_pending_actions(ADMIN_PENDING_ACTIONS)
            await message.answer('✅ Текст соцсетей обновлён.')
            return
        
    if a == 'add_review':
            if message.photo:
                raw = get_setting('reviews_photos', '[]')
                try:
                    photos = json.loads(raw)
                    if not isinstance(photos, list):
                        photos = []
                except Exception:
                    photos = []
                
                file_id = message.photo[-1].file_id
                if file_id not in photos:
                    photos.append(file_id)
                    set_setting('reviews_photos', json.dumps(photos, ensure_ascii=False))
                    ADMIN_PENDING_ACTIONS.pop(username, None)
                    save_pending_actions(ADMIN_PENDING_ACTIONS)
                    await message.answer(f'✅ Отзыв добавлен! Всего отзывов: {len(photos)}')
                else:
                    await message.answer('Этот отзыв уже добавлен.')
            else:
                await message.answer('Пожалуйста, отправьте фотографию отзыва.')
            return
            
    # --- Photo/category & menu editing handlers (single consolidated block) ---
    if a == 'add_photo_cat':
            slug = payload.get('slug')
            if message.photo:
                key = f'portfolio_{slug}'
                raw = get_setting(key, '[]')
                try:
                    photos = json.loads(raw)
                    if not isinstance(photos, list):
                        photos = []
                except Exception:
                    photos = []
                old_len = len(photos)
                file_id = message.photo[-1].file_id
                changed = False
                if file_id not in photos:
                    photos.append(file_id)
                    changed = True
                if changed:
                    set_setting(key, json.dumps(photos, ensure_ascii=False))
                # simplified: respond per photo (album merging removed)
                added = 1 if changed else 0
                await message.answer(f'✅ Добавлено {added}.')
                ADMIN_PENDING_ACTIONS[username] = {'action': 'add_photo_cat', 'payload': {'slug': slug}}
                save_pending_actions(ADMIN_PENDING_ACTIONS)
                return
            else:
                await message.answer('Пришлите фото.')
                return
    
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

