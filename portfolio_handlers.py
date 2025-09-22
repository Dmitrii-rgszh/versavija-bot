from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InputMediaPhoto, Message

from admin_state import ADMIN_PENDING_ACTIONS
from admin_utils import is_admin_view_enabled
from bot_constants import MENU_MESSAGES
from booking_handlers import get_portfolio_categories
from config import bot
from db import (
    get_setting,
    save_pending_actions,
    set_setting,
    toggle_photo_like,
    get_photo_likes_count,
    user_has_liked_photo,
)
from keyboards import (
    build_category_admin_keyboard,
    build_category_delete_keyboard,
    build_category_delete_viewer_keyboard,
    build_category_photo_nav_keyboard,
    build_confirm_delete_all_photos_kb,
    build_confirm_delete_category_kb,
    build_portfolio_keyboard,
    build_undo_category_delete_kb,
    build_undo_photo_delete_kb,
)
from portfolio_state import (
    LAST_CATEGORY_PHOTO,
    UNDO_DELETED_CATEGORY,
    UNDO_DELETED_CATEGORY_PHOTOS,
    UNDO_DELETED_PHOTO,
    reset_last_category_position,
)

portfolio_router = Router(name="portfolio")


def get_portfolio_keyboard_with_likes(slug: str, idx: int, user_id: int) -> InlineKeyboardMarkup:
    """Собрать клавиатуру для просмотра фото с учётом лайков."""
    likes_count = get_photo_likes_count(slug, idx)
    user_has_liked = user_has_liked_photo(slug, idx, user_id)
    return build_category_photo_nav_keyboard(slug, idx, user_id, likes_count, user_has_liked)


@portfolio_router.message(Command(commands=['portfolio']))
async def cmd_portfolio(message: Message) -> None:
    username = (message.from_user.username or "").lstrip("@").lower()
    cats = await get_portfolio_categories()
    is_admin = await is_admin_view_enabled(username, message.from_user.id)
    kb = build_portfolio_keyboard(cats, is_admin=is_admin)
    await message.answer(MENU_MESSAGES["portfolio"], reply_markup=kb)


@portfolio_router.callback_query(F.data == 'portfolio')
async def cb_show_portfolio_menu(query: CallbackQuery) -> None:
    username = (query.from_user.username or "").lstrip("@").lower()
    cats = await get_portfolio_categories()
    is_admin = await is_admin_view_enabled(username, query.from_user.id)
    kb = build_portfolio_keyboard(cats, is_admin=is_admin)
    await query.message.answer(MENU_MESSAGES["portfolio"], reply_markup=kb)


@portfolio_router.callback_query(F.data.startswith('pf:'))
async def cb_show_category(query: CallbackQuery) -> None:
    slug = query.data.split(':', 1)[1]
    cats = await get_portfolio_categories()
    cat = next((c for c in cats if c.get('slug') == slug), None)
    if not cat:
        await query.message.answer('Категория не найдена.')
        return

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
        cycle_key = (query.message.chat.id, slug)
        last_shown = LAST_CATEGORY_PHOTO.get(cycle_key, len(photos))
        if last_shown >= len(photos):
            idx = len(photos) - 1
        else:
            idx = last_shown - 1
            if idx < 0:
                idx = len(photos) - 1

        fid = photos[idx]
        caption = f'📸 {cat.get("text")}'
        try:
            keyboard = get_portfolio_keyboard_with_likes(slug, idx, query.from_user.id)
            await bot.send_photo(chat_id=query.message.chat.id, photo=fid, caption=caption, reply_markup=keyboard)
            LAST_CATEGORY_PHOTO[cycle_key] = idx
            photo_sent = True
        except Exception:
            keyboard = get_portfolio_keyboard_with_likes(slug, 0, query.from_user.id)
            await query.message.answer(f'📸 {cat.get("text")} (ошибка отправки фото)', reply_markup=keyboard)
            photo_sent = True
    else:
        await query.message.answer(f'📸 Категория: {cat.get("text")} (нет фото)')

    username = (query.from_user.username or "").lstrip("@").lower()
    is_admin = await is_admin_view_enabled(username, query.from_user.id)
    if is_admin:
        kb = build_category_admin_keyboard(slug, has_photos=bool(photos))
        await query.message.answer('Управление категорией:', reply_markup=kb)
    elif not photo_sent:
        kb = build_portfolio_keyboard(await get_portfolio_categories(), page=0, is_admin=False)
        await query.message.answer('Категории:', reply_markup=kb)


@portfolio_router.callback_query(F.data.startswith('pf_pic:'))
async def cb_nav_photo(query: CallbackQuery) -> None:
    parts = query.data.split(':')
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

    if not photos:
        await query.message.answer('Нет фото в категории.')
        return

    chat_key = (query.message.chat.id, slug)
    last_idx = LAST_CATEGORY_PHOTO.get(chat_key)
    if last_idx is None:
        idx = len(photos) - 1
    else:
        idx = last_idx - 1
        if idx < 0:
            idx = len(photos) - 1

    fid = photos[idx]
    cat_text = next((c.get('text') for c in await get_portfolio_categories() if c.get('slug') == slug), slug)
    try:
        await query.message.edit_media(InputMediaPhoto(media=fid, caption=f'📸 {cat_text}'))
        keyboard = get_portfolio_keyboard_with_likes(slug, idx, query.from_user.id)
        await query.message.edit_reply_markup(reply_markup=keyboard)
        LAST_CATEGORY_PHOTO[chat_key] = idx
    except Exception as exc:
        logging.warning("Failed to edit_media, fallback new message: %s", exc)
        keyboard = get_portfolio_keyboard_with_likes(slug, idx, query.from_user.id)
        await bot.send_photo(chat_id=query.message.chat.id, photo=fid, caption=f'📸 {cat_text}', reply_markup=keyboard)
        LAST_CATEGORY_PHOTO[chat_key] = idx


@portfolio_router.callback_query(F.data.startswith('like:'))
async def cb_like_photo(query: CallbackQuery) -> None:
    parts = query.data.split(':')
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
    liked = toggle_photo_like(slug, photo_idx, user_id)
    likes_count = get_photo_likes_count(slug, photo_idx)
    user_has_liked = user_has_liked_photo(slug, photo_idx, user_id)

    try:
        keyboard = build_category_photo_nav_keyboard(slug, photo_idx, user_id, likes_count, user_has_liked)
        await query.message.edit_reply_markup(reply_markup=keyboard)
        await query.answer("❤️ Лайк поставлен!" if liked else "💔 Лайк убран")
    except Exception as exc:
        logging.warning("Failed to update like button: %s", exc)
        await query.answer("❤️ Лайк обновлён!")


@portfolio_router.callback_query(F.data.startswith('pf_back_cat:'))
async def cb_back_to_category_admin(query: CallbackQuery) -> None:
    slug = query.data.split(':', 1)[1]
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
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


@portfolio_router.callback_query(F.data.startswith('pf_add:'))
async def cb_add_photo_request(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        await query.message.answer('🚫 Нет доступа.')
        return
    slug = query.data.split(':', 1)[1]
    admin_key = (query.from_user.username or '').lstrip('@').lower()
    ADMIN_PENDING_ACTIONS[admin_key] = {'action': 'add_photo_cat', 'payload': {'slug': slug}}
    save_pending_actions(ADMIN_PENDING_ACTIONS)
    await query.message.answer('Пришлите фото одним сообщением (из галереи).')


@portfolio_router.callback_query(F.data.startswith('pf_del_all_confirm:'))
async def cb_confirm_delete_all(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        await query.message.answer('🚫 Нет доступа.')
        return
    slug = query.data.split(':', 1)[1]
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
    await query.message.answer(
        f'Очистить ВСЕ фото ({len(photos)}) в категории? Это можно будет отменить.',
        reply_markup=build_confirm_delete_all_photos_kb(slug),
    )


@portfolio_router.callback_query(F.data.startswith('pf_del_all_yes:'))
async def cb_delete_all_photos(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        await query.message.answer('🚫 Нет доступа.')
        return
    slug = query.data.split(':', 1)[1]
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
    UNDO_DELETED_CATEGORY_PHOTOS[slug] = photos.copy()
    set_setting(f'portfolio_{slug}', json.dumps([], ensure_ascii=False))
    await query.message.answer(
        f'✅ Все фото ({len(photos)}) удалены.',
        reply_markup=build_undo_photo_delete_kb(slug),
    )
    kb = build_category_admin_keyboard(slug, has_photos=False)
    await query.message.answer('Управление категорией:', reply_markup=kb)


@portfolio_router.callback_query(F.data.startswith('pf_del_all_no:'))
async def cb_cancel_delete_all(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        await query.message.answer('🚫 Нет доступа.')
        return
    await query.message.answer('Удаление отменено.')


@portfolio_router.callback_query(F.data.startswith('pf_del:'))
async def cb_start_delete_mode(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        return
    parts = query.data.split(':')
    if len(parts) < 2:
        return
    slug = parts[1]
    raw = get_setting(f'portfolio_{slug}', '[]')
    try:
        photos = json.loads(raw)
        if not isinstance(photos, list):
            photos = []
    except Exception:
        photos = []
    if not photos:
        await query.message.answer('Нет фото в категории.')
        return
    kb = build_category_delete_keyboard(slug, photos)
    await query.message.answer('Выберите фото для удаления:', reply_markup=kb)


@portfolio_router.callback_query(F.data.startswith('pf_del_idx:'))
async def cb_open_delete_viewer(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        return
    parts = query.data.split(':')
    if len(parts) < 3:
        return
    slug = parts[1]
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
    idx = int(parts[2]) if parts[2].isdigit() else 0
    idx = max(0, min(idx, len(photos) - 1))
    fid = photos[idx]
    try:
        await query.message.edit_media(InputMediaPhoto(media=fid, caption='🗑 Режим удаления'))
        await query.message.edit_reply_markup(reply_markup=build_category_delete_viewer_keyboard(slug, idx))
    except Exception:
        await bot.send_photo(
            chat_id=query.message.chat.id,
            photo=fid,
            caption='🗑 Режим удаления',
            reply_markup=build_category_delete_viewer_keyboard(slug, idx),
        )


@portfolio_router.callback_query(F.data.startswith('pf_delnav:'))
async def cb_delete_nav(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        return
    parts = query.data.split(':')
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

    if len(photos) > 1:
        candidates = [i for i in range(len(photos)) if i != cur_idx]
        if not candidates:
            candidates = list(range(len(photos)))
        new_idx = random.choice(candidates)
    else:
        new_idx = 0
    fid = photos[new_idx]
    try:
        await query.message.edit_media(InputMediaPhoto(media=fid, caption='🗑 Режим удаления'))
        await query.message.edit_reply_markup(reply_markup=build_category_delete_viewer_keyboard(slug, new_idx))
    except Exception:
        await bot.send_photo(
            chat_id=query.message.chat.id,
            photo=fid,
            caption='🗑 Режим удаления',
            reply_markup=build_category_delete_viewer_keyboard(slug, new_idx),
        )


@portfolio_router.callback_query(F.data.startswith('pf_delcurr:'))
async def cb_delete_current_photo(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        return
    parts = query.data.split(':')
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
    if not photos or not (0 <= del_idx < len(photos)):
        await query.message.answer('Индекс вне диапазона.')
        return

    removed = photos.pop(del_idx)
    UNDO_DELETED_PHOTO[slug] = removed
    set_setting(key, json.dumps(photos, ensure_ascii=False))
    next_idx = 0 if not photos else min(del_idx, len(photos) - 1)
    if photos:
        fid = photos[next_idx]
        try:
            await query.message.edit_media(
                InputMediaPhoto(media=fid, caption='🗑 Удалено. Следующее.'),
                reply_markup=build_category_delete_viewer_keyboard(slug, next_idx),
            )
        except Exception:
            await bot.send_photo(
                chat_id=query.message.chat.id,
                photo=fid,
                caption='🗑 Удалено. Следующее.',
                reply_markup=build_category_delete_viewer_keyboard(slug, next_idx),
            )
        await query.message.answer('Фото удалено. Можно восстановить последнее.', reply_markup=build_undo_photo_delete_kb(slug))
    else:
        await query.message.answer('Все фото удалены.')
        kb = build_category_admin_keyboard(slug, has_photos=False)
        await query.message.answer('Управление категорией:', reply_markup=kb)


@portfolio_router.callback_query(F.data.startswith('pf_del_done:'))
async def cb_delete_done(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        return
    slug = query.data.split(':', 1)[1]
    raw = get_setting(f'portfolio_{slug}', '[]')
    try:
        photos = json.loads(raw)
        if not isinstance(photos, list):
            photos = []
    except Exception:
        photos = []
    kb = build_category_admin_keyboard(slug, has_photos=bool(photos))
    await query.message.answer('Управление категорией:', reply_markup=kb)


@portfolio_router.callback_query(F.data.startswith('pf_page:'))
async def cb_portfolio_page(query: CallbackQuery) -> None:
    part = query.data.split(':', 1)[1]
    if part == 'noop':
        return
    try:
        page = int(part)
    except Exception:
        page = 0
    cats = await get_portfolio_categories()
    is_admin = await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id)
    kb = build_portfolio_keyboard(cats, page=page, is_admin=is_admin)
    try:
        await query.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        await query.message.answer(MENU_MESSAGES["portfolio"], reply_markup=kb)


@portfolio_router.callback_query(F.data == 'pf_cat_new')
async def cb_new_category(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        await query.message.answer('🚫 Нет доступа.')
        return
    admin_key = (query.from_user.username or '').lstrip('@').lower()
    ADMIN_PENDING_ACTIONS[admin_key] = {'action': 'new_category', 'payload': {}}
    save_pending_actions(ADMIN_PENDING_ACTIONS)
    await query.message.answer('Введите название новой категории:')


@portfolio_router.callback_query(F.data.startswith('pf_cat_ren:'))
async def cb_rename_category(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        await query.message.answer('🚫 Нет доступа.')
        return
    slug = query.data.split(':', 1)[1]
    cats = await get_portfolio_categories()
    cat = next((c for c in cats if c.get('slug') == slug), None)
    if not cat:
        await query.message.answer('Категория не найдена.')
        return
    admin_key = (query.from_user.username or '').lstrip('@').lower()
    ADMIN_PENDING_ACTIONS[admin_key] = {'action': 'rename_category', 'payload': {'slug': slug}}
    save_pending_actions(ADMIN_PENDING_ACTIONS)
    await query.message.answer(f"Введите новое название для категории '{cat.get('text')}'")


@portfolio_router.callback_query(F.data.startswith('pf_cat_del:'))
async def cb_delete_category_confirm(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        await query.message.answer('🚫 Нет доступа.')
        return
    slug = query.data.split(':', 1)[1]
    cats = await get_portfolio_categories()
    cat = next((c for c in cats if c.get('slug') == slug), None)
    if not cat:
        await query.message.answer('Категория не найдена.')
        return
    await query.message.answer(
        f"Подтвердите удаление категории '{cat.get('text')}' и всех её фото.",
        reply_markup=build_confirm_delete_category_kb(slug),
    )


@portfolio_router.callback_query(F.data.startswith('pf_cat_del_yes:'))
async def cb_delete_category(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        await query.message.answer('🚫 Нет доступа.')
        return
    slug = query.data.split(':', 1)[1]
    cats = await get_portfolio_categories()
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


@portfolio_router.callback_query(F.data.startswith('pf_cat_del_no:'))
async def cb_cancel_delete_category(query: CallbackQuery) -> None:
    await query.message.answer('Удаление отменено.')


@portfolio_router.callback_query(F.data.startswith('pf_undo_cat:'))
async def cb_undo_category(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        return
    slug = query.data.split(':', 1)[1]
    cat = UNDO_DELETED_CATEGORY.pop(slug, None)
    photos_restore = UNDO_DELETED_CATEGORY_PHOTOS.pop(slug, None)
    if not cat:
        await query.message.answer('Нечего восстанавливать.')
        return
    cats = await get_portfolio_categories()
    cats.append(cat)
    set_setting('portfolio_categories', json.dumps(cats, ensure_ascii=False))
    if photos_restore is not None:
        set_setting(f'portfolio_{slug}', json.dumps(photos_restore, ensure_ascii=False))
    kb = build_portfolio_keyboard(cats, is_admin=True)
    await query.message.answer('✅ Категория восстановлена.', reply_markup=kb)


@portfolio_router.callback_query(F.data.startswith('pf_undo_photo:'))
async def cb_undo_photo(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled((query.from_user.username or "").lstrip("@").lower(), query.from_user.id):
        return
    slug = query.data.split(':', 1)[1]
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


async def handle_portfolio_pending_action(
    message: Message,
    username: str,
    action: str,
    payload: Dict[str, Any],
) -> bool:
    """Обработать отложенные действия, связанные с портфолио."""
    if action == 'new_category':
        if not message.text:
            await message.answer('Ожидаю название категории. Попробуйте снова.')
            return True
        title = message.text.strip()
        if not title:
            await message.answer('Название не может быть пустым.')
            ADMIN_PENDING_ACTIONS.pop(username, None)
            save_pending_actions(ADMIN_PENDING_ACTIONS)
            return True
        from utils import normalize_callback

        slug = normalize_callback(title)
        cats = await get_portfolio_categories()
        if any(c.get('slug') == slug for c in cats):
            await message.answer(f'Категория со slug "{slug}" уже существует. Измените название.')
            return True
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
        return True

    if action == 'rename_category':
        if not message.text:
            await message.answer('Ожидаю новое название. Попробуйте снова.')
            return True
        new_title = message.text.strip()
        if not new_title:
            await message.answer('Название не может быть пустым.')
            ADMIN_PENDING_ACTIONS.pop(username, None)
            save_pending_actions(ADMIN_PENDING_ACTIONS)
            return True
        slug = payload.get('slug')
        cats = await get_portfolio_categories()
        cat = next((c for c in cats if c.get('slug') == slug), None)
        if not cat:
            await message.answer('Категория не найдена.')
            ADMIN_PENDING_ACTIONS.pop(username, None)
            save_pending_actions(ADMIN_PENDING_ACTIONS)
            return True
        old_title = cat.get('text')
        cat['text'] = new_title
        set_setting('portfolio_categories', json.dumps(cats, ensure_ascii=False))
        ADMIN_PENDING_ACTIONS.pop(username, None)
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await message.answer(f'✅ Категория "{old_title}" переименована в "{new_title}".')
        kb = build_portfolio_keyboard(cats, is_admin=True)
        await message.answer('Обновлённый список категорий:', reply_markup=kb)
        return True

    if action == 'add_photo_cat':
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
            file_id = message.photo[-1].file_id
            changed = False
            if file_id not in photos:
                photos.append(file_id)
                changed = True
            if changed:
                set_setting(key, json.dumps(photos, ensure_ascii=False))
                reset_last_category_position(slug)
            added = 1 if changed else 0
            await message.answer(f'✅ Добавлено {added}.')
            ADMIN_PENDING_ACTIONS[username] = {'action': 'add_photo_cat', 'payload': {'slug': slug}}
            save_pending_actions(ADMIN_PENDING_ACTIONS)
            return True
        await message.answer('Пришлите фото.')
        return True

    return False


__all__ = [
    "portfolio_router",
    "get_portfolio_keyboard_with_likes",
    "handle_portfolio_pending_action",
]
