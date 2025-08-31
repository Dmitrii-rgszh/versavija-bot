import logging
import pathlib
import json
import os
from pathlib import Path

# track last shown photo index per chat+category to avoid repeats
LAST_CATEGORY_PHOTO: dict[tuple[int, str], int] = {}
# track set of already shown indices for cycle (chat, category)
SEEN_CATEGORY_PHOTOS: dict[tuple[int, str], set] = {}
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from aiogram.filters import Command

from config import bot, dp, ADMIN_IDS
from db import get_setting, set_setting, get_menu, save_menu, get_pending_actions, save_pending_actions
from db import add_booking, is_slot_taken, get_bookings_between, get_booking, update_booking_status, clear_all_bookings
from db import get_active_booking_for_user, update_booking_time_and_category
from keyboards import (
    build_main_keyboard_from_menu,
    admin_panel_keyboard,
    build_menu_edit_kb,
    build_confirm_delete_kb,
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
    ADMIN_USERNAMES,
)

# In-memory state containers (not persisted unless explicitly written via set_setting)
BOOKING_FLOW_MSGS: dict[int, list[int]] = {}
UNDO_DELETED_CATEGORY: dict[str, dict] = {}
UNDO_DELETED_CATEGORY_PHOTOS: dict[str, list] = {}
UNDO_DELETED_PHOTO: dict[str, str] = {}

WELCOME_TEXT = (
    "👋 Приветствуем в официальном Telegram-боте профессионального фотографа!\n\n"
    "📸 Здесь вы можете ознакомиться с портфолио, выбрать оптимальный пакет услуг и записаться онлайн на фотосессию.\n\n"
    "✨ Погрузитесь в мир качественной фотографии, подчеркните свою индивидуальность и сохраните лучшие моменты жизни!\n\n"
    "🔎 Удобный выбор пакетов, прозрачные цены и быстрая запись — всё для вашего комфорта.\n\n"
    "💬 Начните прямо сейчас: выберите интересующий пакет и забронируйте дату фотосессии!\n\n"
    "#фотограф #фотосессия #портфолио #онлайнзапись #фотосъемка #услугифотографа"
)

# default menu used when DB has no saved menu
DEFAULT_MENU = [
    {"text": "Портфолио", "callback": "portfolio"},
    {"text": "Услуги и цены", "callback": "services"},
    {"text": "Онлайн-запись", "callback": "booking"},
    {"text": "Отзывы", "callback": "reviews"},
    {"text": "Соцсети", "callback": "social"},
]

# default portfolio categories
DEFAULT_PORTFOLIO_CATEGORIES = [
    {"text": "Семейная", "slug": "family"},
    {"text": "Love Story", "slug": "love_story"},
    {"text": "Индивидуальная", "slug": "personal"},
    {"text": "Репортажная (банкеты, мероприятия)", "slug": "reportage"},
    {"text": "Свадебная", "slug": "wedding"},
    {"text": "Lingerie (будуарная)", "slug": "lingerie"},
    {"text": "Детская (школы/садики)", "slug": "children"},
    {"text": "Мама с ребёнком", "slug": "mom_child"},
    {"text": "Крещение", "slug": "baptism"},
    {"text": "Венчание", "slug": "wedding_church"},
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

# IDs of users for whom we show dynamic booking status button (can be extended)
def _load_booking_status_user_ids() -> set[int]:
    raw = get_setting('booking_status_user_ids', '') or ''
    ids = set()
    for part in raw.split(','):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids

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
            BotCommand(command='help', description='Справка'),
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
ADMIN_PENDING_ACTIONS: dict = get_pending_actions()


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
        await message.answer('Главное меню обновлено.', reply_markup=kb)


@dp.message(Command(commands=['refreshcommands','synccommands','sync']))
async def refresh_commands(message: Message):
    username = (message.from_user.username or '').lstrip('@').lower()
    if not _user_is_admin(username, message.from_user.id):
        return
    await _set_static_commands()
    await message.answer('✅ Команды: /start /help /adminmode.')


@dp.message(Command(commands=['start', 'help']))
async def send_welcome(message: Message):
    username = (message.from_user.username or "").lstrip("@").lower()
    user_id = message.from_user.id
    is_admin = is_admin_view_enabled(username, user_id)
    # load menu from DB (default menu if none)
    menu = get_menu(DEFAULT_MENU)
    keyboard = build_main_keyboard_from_menu(menu, is_admin)
    keyboard = _inject_booking_status_button(keyboard, user_id)
    await _set_static_commands()

    # Загружаем текст и image_file_id из БД, если они заданы
    db_text = get_setting('welcome_text', WELCOME_TEXT)
    image_file_id = get_setting('welcome_image_file_id', None)

    # если в БД есть file_id — попытаемся отправить его как фото
    if image_file_id:
        try:
            await message.answer_photo(photo=image_file_id, caption=db_text)
            await bot.send_message(chat_id=message.chat.id, text="Выберите действие ниже:", reply_markup=keyboard)
            return
        except Exception:
            logging.exception('Failed to send photo by file_id, will try local file or text')

    media_path = pathlib.Path(__file__).parent / 'media' / 'greetings.png'
    if media_path.exists():
        photo = FSInputFile(pathlib.Path(media_path))
        await message.answer_photo(photo=photo, caption=db_text)
    else:
        await message.answer(db_text)

    try:
        await bot.send_message(chat_id=message.chat.id, text="Выберите действие ниже:", reply_markup=keyboard)
        logging.info("Keyboard sent to chat %s (user=%s)", message.chat.id, username)
    except Exception:
        logging.exception("Failed to send keyboard via bot.send_message, falling back to message.answer")
        try:
            await message.answer("Выберите действие ниже:", reply_markup=keyboard)
        except Exception:
            logging.exception("Fallback message.answer also failed")


    # End of send_welcome


@dp.callback_query()
async def handle_callback(query: CallbackQuery):
    data_raw = query.data or ""
    data = data_raw.lower()
    username = (query.from_user.username or "").lstrip("@").lower()

    # quick debug log to capture what callback data arrives from the client
    logging.info("HANDLER VERSION vDel2 | user=%s raw=%s lowered=%s", username, data_raw, data)

    try:
        await query.answer()
    except Exception:
        pass

    # helper: resolve an identifier (either numeric index or item callback) to index
    def resolve_idx(token: str) -> int | None:
        """token may be '123' or '::ident' or 'ident' depending on keyboard; return index or None"""
        menu = get_menu(DEFAULT_MENU)
        # strip possible '::' prefix
        if token.startswith('::'):
            token = token[2:]
        logging.info("resolve_idx called with token=%s", token)
        # numeric?
        try:
            i = int(token)
        except Exception:
            i = None
        if isinstance(i, int):
            if 0 <= i < len(menu):
                logging.info("resolve_idx returning numeric index=%s for token=%s", i, token)
                return i
        # otherwise search by callback identifier
        for i, m in enumerate(menu):
            if m.get('callback') == token:
                logging.info("resolve_idx found index=%s for token=%s", i, token)
                return i
        return None
    
    def extract_token(data_str: str) -> str:
        """Return token part for callbacks supporting both '::' and ':' delimiters."""
        if '::' in data_str:
            return data_str.split('::', 1)[1]
        if ':' in data_str:
            return data_str.split(':', 1)[1]
        return data_str

    # public actions
    if data == "portfolio":
        cats = get_portfolio_categories()
        is_admin = is_admin_view_enabled(username, query.from_user.id)
        kb = build_portfolio_keyboard(cats, is_admin=is_admin)
        await query.message.answer("📁 Выберите категорию портфолио:", reply_markup=kb)
        return
    if data == "services":
        kb = build_services_keyboard()
        await query.message.answer("💼 Услуги и цены: выберите категорию", reply_markup=kb)
        return
    
    if data == "wedding_packages":
        # Show first wedding package
        package = WEDDING_PACKAGES[0]
        kb = build_wedding_packages_nav_keyboard(0)
        await query.message.answer(package["text"], reply_markup=kb)
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
        await query.message.answer("Выберите действие:", reply_markup=keyboard)
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
            import random
            cycle_key = (query.message.chat.id, 'reviews')
            seen = SEEN_CATEGORY_PHOTOS.get(cycle_key, set())
            if len(seen) >= len(photos):
                seen.clear()
            available = [i for i in range(len(photos)) if i not in seen]
            if not available:
                available = list(range(len(photos)))
            idx = random.choice(available)
            fid = photos[idx]
            caption = f'⭐ Отзыв {idx+1} из {len(photos)}'
            try:
                await bot.send_photo(chat_id=query.message.chat.id, photo=fid, caption=caption, reply_markup=build_reviews_nav_keyboard(idx))
                LAST_CATEGORY_PHOTO[(query.message.chat.id, 'reviews')] = idx
                seen.add(idx)
                SEEN_CATEGORY_PHOTOS[cycle_key] = seen
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
            import random
            cycle_key = (query.message.chat.id, slug)
            seen = SEEN_CATEGORY_PHOTOS.get(cycle_key, set())
            if len(seen) >= len(photos):
                seen.clear()
            available = [i for i in range(len(photos)) if i not in seen]
            if not available:
                available = list(range(len(photos)))
            idx = random.choice(available)
            fid = photos[idx]
            caption = f'📸 {cat.get("text")}'
            try:
                await bot.send_photo(chat_id=query.message.chat.id, photo=fid, caption=caption, reply_markup=build_category_photo_nav_keyboard(slug, idx))
                LAST_CATEGORY_PHOTO[(query.message.chat.id, slug)] = idx
                seen.add(idx)
                SEEN_CATEGORY_PHOTOS[cycle_key] = seen
                photo_sent = True
            except Exception:
                await query.message.answer(f'📸 {cat.get("text")} (ошибка отправки фото)', reply_markup=build_category_photo_nav_keyboard(slug, 0))
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
            import random
            chat_key = (query.message.chat.id, slug)
            last_idx = LAST_CATEGORY_PHOTO.get(chat_key)
            cycle_key = (query.message.chat.id, slug)
            seen = SEEN_CATEGORY_PHOTOS.get(cycle_key, set())
            if last_idx is not None:
                seen.add(last_idx)
            if len(seen) >= len(photos):
                seen = set()  # reset cycle
            remaining = [i for i in range(len(photos)) if i not in seen]
            if not remaining:
                remaining = list(range(len(photos)))
            idx = random.choice(remaining)
            fid = photos[idx]
            # resolve category display text
            cat_text = next((c.get('text') for c in get_portfolio_categories() if c.get('slug') == slug), slug)
            from aiogram.types import InputMediaPhoto
            try:
                logging.info("Attempting to edit_media for photo navigation: slug=%s, idx=%s", slug, idx)
                await query.message.edit_media(InputMediaPhoto(media=fid, caption=f'📸 {cat_text}'))
                await query.message.edit_reply_markup(reply_markup=build_category_photo_nav_keyboard(slug, idx))
                logging.info("Successfully edited media for photo navigation")
                LAST_CATEGORY_PHOTO[chat_key] = idx
                seen.add(idx)
                SEEN_CATEGORY_PHOTOS[cycle_key] = seen
            except Exception as e:
                # fallback new message
                logging.warning("Failed to edit_media, falling back to new message: %s", e)
                await bot.send_photo(chat_id=query.message.chat.id, photo=fid, caption=f'📸 {cat_text}', reply_markup=build_category_photo_nav_keyboard(slug, idx))
                LAST_CATEGORY_PHOTO[chat_key] = idx
                seen.add(idx)
                SEEN_CATEGORY_PHOTOS[cycle_key] = seen
        else:
            await query.message.answer('Нет фото в категории.')
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
            await query.message.answer('Выберите фото для удаления:', reply_markup=kb)
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
                    await query.message.edit_media(InputMediaPhoto(media=fid, caption='🗑 Удалено. Следующее.'))
                    await query.message.edit_reply_markup(reply_markup=build_category_delete_viewer_keyboard(slug, next_idx))
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
            await query.message.answer('📁 Выберите категорию портфолио:', reply_markup=kb)
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
                import random
                chat_key = (query.message.chat.id, 'reviews')
                last_idx = LAST_CATEGORY_PHOTO.get(chat_key)
                cycle_key = (query.message.chat.id, 'reviews')
                seen = SEEN_CATEGORY_PHOTOS.get(cycle_key, set())
                if last_idx is not None:
                    seen.add(last_idx)
                if len(seen) >= len(photos):
                    seen = set()  # reset cycle
                remaining = [i for i in range(len(photos)) if i not in seen]
                if not remaining:
                    remaining = list(range(len(photos)))
                idx = random.choice(remaining)
                fid = photos[idx]
                caption = f'⭐ Отзыв {idx+1} из {len(photos)}'
                from aiogram.types import InputMediaPhoto
                try:
                    await query.message.edit_media(InputMediaPhoto(media=fid, caption=caption))
                    await query.message.edit_reply_markup(reply_markup=build_reviews_nav_keyboard(idx))
                    LAST_CATEGORY_PHOTO[chat_key] = idx
                    seen.add(idx)
                    SEEN_CATEGORY_PHOTOS[cycle_key] = seen
                except Exception:
                    # fallback new message
                    await bot.send_photo(chat_id=query.message.chat.id, photo=fid, caption=caption, reply_markup=build_reviews_nav_keyboard(idx))
                    LAST_CATEGORY_PHOTO[chat_key] = idx
                    seen.add(idx)
                    SEEN_CATEGORY_PHOTOS[cycle_key] = seen
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
        await query.message.answer(f'Выберите отзыв для удаления (всего: {len(photos)}):', reply_markup=kb)
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
        await query.message.answer('⬅️ Возврат в главное меню.', reply_markup=kb)
        return

    # Booking status button (only for special users)
    if data == 'booking_status':
        bk = get_active_booking_for_user(query.from_user.id)
        if not bk:
            # refresh menu (maybe was cancelled)
            menu = get_menu(DEFAULT_MENU)
            kb = build_main_keyboard_from_menu(menu, is_admin_view_enabled(username, query.from_user.id))
            kb = _inject_booking_status_button(kb, query.from_user.id)
            await query.message.answer('Нет активной записи.', reply_markup=kb)
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
    async def _send_booking_step(q: CallbackQuery, text: str, kb: InlineKeyboardMarkup | None = None):
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
        dates = [today + timedelta(days=i) for i in range(30)]
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
        await _send_booking_step(query, 'Выберите категорию фотосессии:', InlineKeyboardMarkup(inline_keyboard=rows))
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
            await query.message.answer('Выберите дату:', reply_markup=build_booking_date_kb())
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
        await bot.send_message(query.message.chat.id, 'Главное меню обновлено:', reply_markup=kb_main)
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
        await query.message.answer('Запись отменена.', reply_markup=kb)
        return

    # admin actions
    if data == 'admin':
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        kb = admin_panel_keyboard(is_admin_view_enabled(username, query.from_user.id))
        await query.message.answer("🔒 Панель администрирования: выберите действие:", reply_markup=kb)
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

    # menu management entrypoint
    if data == 'admin_manage_menu':
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        menu = get_menu(DEFAULT_MENU)
        kb = build_menu_edit_kb(menu)
        await query.message.answer("🛠️ Управление меню:", reply_markup=kb)
        return

    # add menu
    if data == 'add_menu':
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        ADMIN_PENDING_ACTIONS[username] = {'action': 'add_menu', 'payload': {}}
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await query.message.answer('Пришлите текст для новой кнопки (одним сообщением).')
        return

    if data == 'add_menu_manual':
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        ADMIN_PENDING_ACTIONS[username] = {'action': 'add_menu_manual', 'payload': {}}
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await query.message.answer('Пришлите текст для новой кнопки (одним сообщением). Затем я попрошу callback_data.')
        return

    if data == 'view_menu':
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        menu = get_menu(DEFAULT_MENU)
        pretty = json.dumps(menu, ensure_ascii=False, indent=2)
        await query.message.answer(f'Текущая структура меню (JSON):\n{pretty}')
        return

    # edit/delete menu handlers
    if data.startswith('edit_menu:') or data.startswith('edit_menu::'):
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        token = extract_token(data)
        idx = resolve_idx(token)
        if idx is None:
            await query.message.answer('Неверный идентификатор кнопки.')
            return
        menu = get_menu(DEFAULT_MENU)
        ADMIN_PENDING_ACTIONS[username] = {'action': 'edit_menu', 'payload': {'idx': idx}}
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await query.message.answer(f'Отправьте новый текст для кнопки "{menu[idx].get("text")}"')
        return

    if data.startswith('edit_callback:') or data.startswith('edit_callback::'):
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        token = extract_token(data)
        idx = resolve_idx(token)
        if idx is None:
            await query.message.answer('Неверный идентификатор кнопки.')
            return
        menu = get_menu(DEFAULT_MENU)
        ADMIN_PENDING_ACTIONS[username] = {'action': 'edit_callback', 'payload': {'idx': idx}}
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await query.message.answer(f'Пришлите новый callback_data для кнопки "{menu[idx].get("text")}" (латинские буквы, цифры, _ и - будут сохранены).')
        return

    # Immediate delete on prompt to simplify UX: remove the item when "Удалить" pressed
    if data.startswith('prompt_delete:') or data.startswith('prompt_delete::'):
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        token = extract_token(data)
        idx = resolve_idx(token)
        if idx is None:
            await query.message.answer('Неверный идентификатор кнопки.')
            return
        try:
            menu = get_menu(DEFAULT_MENU)
            logging.info("DELETE FLOW ENTERED token=%s idx=%s menu_before=%s", token, idx, json.dumps(menu, ensure_ascii=False))
            removed = menu.pop(idx)
            save_menu(menu)
            logging.info("DELETE FLOW SUCCESS token=%s removed=%s menu_after=%s", token, removed, json.dumps(menu, ensure_ascii=False))
            await query.message.answer(f'✅ Кнопка "{removed.get("text")}" удалена.')
            kb = build_menu_edit_kb(menu)
            await query.message.answer('Обновлённое меню:', reply_markup=kb)
            save_pending_actions(ADMIN_PENDING_ACTIONS)
        except Exception:
            logging.exception("Failed to delete menu item token=%s idx=%s", token, idx)
            await query.message.answer('Произошла ошибка при удалении кнопки.')
        return

    if data.startswith('move_up:') or data.startswith('move_down:') or data.startswith('move_up::') or data.startswith('move_down::'):
        if not is_admin_view_enabled(username, query.from_user.id):
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        token = extract_token(data)
        idx = resolve_idx(token)
        if idx is None:
            await query.message.answer('Неверный идентификатор кнопки.')
            return
        menu = get_menu(DEFAULT_MENU)
        n = len(menu)
        if idx < 0 or idx >= n:
            await query.message.answer('Индекс вне диапазона.')
            return
        if data.startswith('move_up') and idx > 0:
            menu[idx-1], menu[idx] = menu[idx], menu[idx-1]
            save_menu(menu)
            await query.message.answer('Кнопка перемещена вверх.')
        elif data.startswith('move_down') and idx < n-1:
            menu[idx+1], menu[idx] = menu[idx], menu[idx+1]
            save_menu(menu)
            await query.message.answer('Кнопка перемещена вниз.')
        else:
            await query.message.answer('Нельзя переместить дальше.')
        kb = build_menu_edit_kb(menu)
        await query.message.answer('Обновлённое меню:', reply_markup=kb)
        return

    if data == 'sort_defaults_first':
        if username not in ADMIN_USERNAMES:
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        menu = get_menu(DEFAULT_MENU)
        defaults = ["portfolio","services","booking","reviews","social"]
        default_items = [m for key in defaults for m in menu if m.get('callback')==key]
        other_items = [m for m in menu if m.get('callback') not in defaults]
        new_menu = default_items + other_items
        save_menu(new_menu)
        await query.message.answer('Меню отсортировано: дефолты вынесены в начало.')
        kb = build_menu_edit_kb(new_menu)
        await query.message.answer('Обновлённое меню:', reply_markup=kb)
        return

    # (confirm_delete / delete_menu branches removed — immediate deletion used)

    if data == 'admin_change_text':
        if username not in ADMIN_USERNAMES:
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        ADMIN_PENDING_ACTIONS[username] = 'change_text'
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await query.message.answer('Отправьте новый текст приветствия в сообщении (plain text).')
        return

    if data == 'admin_change_image':
        if username not in ADMIN_USERNAMES:
            await query.message.answer("🚫 У вас нет доступа к администрированию.")
            return
        ADMIN_PENDING_ACTIONS[username] = 'change_image'
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await query.message.answer('Пришлите изображение, которое хотите установить как приветственное (я сохраню file_id).')
        return


@dp.message()
async def handle_admin_pending(message: Message):
    username = (message.from_user.username or "").lstrip("@").lower()
    # allow only if admin mode ON (else ignore silently)
    if not is_admin_view_enabled(username, message.from_user.id):
        return

    action = ADMIN_PENDING_ACTIONS.get(username)
    if not action:
        return

    if action == 'change_text':
        if not message.text:
            await message.answer('Ожидаю текст. Пожалуйста, пришлите новый текст приветствия.')
            return
        set_setting('welcome_text', message.text)
        ADMIN_PENDING_ACTIONS.pop(username, None)
        await message.answer('✅ Текст приветствия обновлён.')
        return
    # menu add/edit & category/photo flows
    if action and isinstance(action, dict):
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
    if a == 'add_menu':
            # message.text -> text for new button; generate callback from slug
            if not message.text:
                await message.answer('Ожидаю текст для кнопки. Пришлите текст одним сообщением.')
                return
            text = message.text.strip()
            if not text:
                await message.answer('Текст не может быть пустым. Отмена.')
                ADMIN_PENDING_ACTIONS.pop(username, None)
                save_pending_actions(ADMIN_PENDING_ACTIONS)
                return
            callback = normalize_callback(text)
            menu = get_menu(DEFAULT_MENU)
            # check duplicate callbacks
            callbacks = {m.get('callback') for m in menu}
            if callback in callbacks:
                await message.answer(f'Ошибка: callback "{callback}" уже существует. Измените текст или используйте ручной режим.')
                return
            menu.append({'text': text, 'callback': callback})
            save_menu(menu)
            # no extra side-effects
            ADMIN_PENDING_ACTIONS.pop(username, None)
            save_pending_actions(ADMIN_PENDING_ACTIONS)
            await message.answer(f'✅ Кнопка "{text}" добавлена.')
            return
    if a == 'add_menu_manual':
            # first step: we expect the text for the button, then ask for callback_data
            if not message.text:
                await message.answer('Ожидаю текст для кнопки. Пришлите текст одним сообщением.')
                return
            text = message.text.strip()
            if not text:
                await message.answer('Текст не может быть пустым. Отмена.')
                ADMIN_PENDING_ACTIONS.pop(username, None)
                save_pending_actions(ADMIN_PENDING_ACTIONS)
                return
            # store text in payload and ask for callback_data
            ADMIN_PENDING_ACTIONS[username] = {'action': 'add_menu_manual_submit', 'payload': {'text': text}}
            save_pending_actions(ADMIN_PENDING_ACTIONS)
            await message.answer('Теперь пришлите желаемый callback_data для этой кнопки (латиница, цифры, подчеркивания).')
            return
    if a == 'add_menu_manual_submit':
            # expecting payload: {'text': ..., 'callback': ...}
            text = payload.get('text')
            callback = payload.get('callback')
            # If callback not yet provided, treat incoming message as the callback_data
            if not callback:
                if not message.text:
                    await message.answer('Ожидаю callback_data (текст). Отмена.')
                    ADMIN_PENDING_ACTIONS.pop(username, None)
                    save_pending_actions(ADMIN_PENDING_ACTIONS)
                    return
                callback = normalize_callback(message.text.strip())
            if not text or not callback:
                await message.answer('Нет текста или callback_data. Отмена.')
                ADMIN_PENDING_ACTIONS.pop(username, None)
                save_pending_actions(ADMIN_PENDING_ACTIONS)
                return
            # normalize callback and validate
            callback = normalize_callback(callback)
            menu = get_menu(DEFAULT_MENU)
            callbacks = {m.get('callback') for m in menu}
            if callback in callbacks:
                await message.answer(f'Ошибка: callback "{callback}" уже существует. Отмена.')
                ADMIN_PENDING_ACTIONS.pop(username, None)
                save_pending_actions(ADMIN_PENDING_ACTIONS)
                return
            menu.append({'text': text, 'callback': callback})
            save_menu(menu)
            # no extra side-effects
            ADMIN_PENDING_ACTIONS.pop(username, None)
            save_pending_actions(ADMIN_PENDING_ACTIONS)
            await message.answer(f'✅ Кнопка "{text}" с callback "{callback}" добавлена.')
            return
    if a == 'edit_menu':
            idx = payload.get('idx')
            if idx is None:
                await message.answer('Нет индекса для редактирования.')
                return
            if not message.text:
                await message.answer('Ожидаю текст для обновления кнопки.')
                return
            menu = get_menu(DEFAULT_MENU)
            if idx < 0 or idx >= len(menu):
                await message.answer('Индекс вне диапазона.')
                ADMIN_PENDING_ACTIONS.pop(username, None)
                return
            new_text = message.text.strip()
            if not new_text:
                await message.answer('Текст не может быть пустым. Отмена.')
                ADMIN_PENDING_ACTIONS.pop(username, None)
                save_pending_actions(ADMIN_PENDING_ACTIONS)
                return
            # check that new callback (derived) won't duplicate existing callbacks, unless it's the same button
            new_callback = normalize_callback(new_text)
            current_callback = menu[idx].get('callback')
            callbacks = {i for i in (m.get('callback') for m in menu) if i}
            if new_callback != current_callback and new_callback in callbacks:
                await message.answer(f'Ошибка: при преобразовании текста в callback "{new_callback}" обнаружен дубликат. Используйте ручное редактирование.')
                return
            old = menu[idx].get('text')
            menu[idx]['text'] = new_text
            save_menu(menu)
            # no extra side-effects
            ADMIN_PENDING_ACTIONS.pop(username, None)
            await message.answer(f'✅ Кнопка "{old}" -> "{menu[idx]["text"]}" обновлена.')
            return
    if a == 'edit_callback':
            idx = payload.get('idx')
            if idx is None:
                await message.answer('Нет индекса для редактирования callback.')
                return
            if not message.text:
                await message.answer('Ожидаю текст с новым callback_data.')
                return
            new_cb = normalize_callback(message.text.strip())
            menu = get_menu(DEFAULT_MENU)
            if idx < 0 or idx >= len(menu):
                await message.answer('Индекс вне диапазона.')
                ADMIN_PENDING_ACTIONS.pop(username, None)
                save_pending_actions(ADMIN_PENDING_ACTIONS)
                return
            callbacks = {m.get('callback') for m in menu}
            current_cb = menu[idx].get('callback')
            if new_cb != current_cb and new_cb in callbacks:
                await message.answer(f'Ошибка: callback "{new_cb}" уже используется. Выберите другой.')
                return
            menu[idx]['callback'] = new_cb
            save_menu(menu)
            # no extra side-effects
            ADMIN_PENDING_ACTIONS.pop(username, None)
            save_pending_actions(ADMIN_PENDING_ACTIONS)
            await message.answer(f'✅ callback для "{menu[idx].get("text")}" обновлён -> "{new_cb}"')
            return
    elif action == 'change_image':
        photo = None
        if message.photo:
            photo = message.photo[-1]
        elif message.document and message.document.mime_type.startswith('image'):
            file_id = message.document.file_id
            set_setting('welcome_image_file_id', file_id)
            ADMIN_PENDING_ACTIONS.pop(username, None)
            await message.answer('✅ Картинка приветствия обновлена (file_id сохранён).')
            return

        if not photo:
            await message.answer('Ожидаю изображение (photo). Пришлите, пожалуйста, картинку.')
            return

        file_id = photo.file_id
        set_setting('welcome_image_file_id', file_id)
        ADMIN_PENDING_ACTIONS.pop(username, None)
        await message.answer('✅ Картинка приветствия обновлена (file_id сохранён).')

