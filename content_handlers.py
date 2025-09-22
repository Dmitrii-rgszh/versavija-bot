from __future__ import annotations

import json
import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from admin_state import ADMIN_PENDING_ACTIONS
from admin_utils import is_admin_view_enabled
from bot_constants import MENU_MESSAGES
from config import bot
from db import get_setting, save_pending_actions, set_setting
from keyboards import (
    build_reviews_admin_keyboard,
    build_reviews_delete_keyboard,
    build_reviews_nav_keyboard,
    build_social_admin_keyboard,
)
from portfolio_state import LAST_CATEGORY_PHOTO, reset_last_category_position

content_router = Router(name="content")
REVIEW_PENDING_USERS: set[int] = set()

_DEFAULT_SOCIAL_TEXT = """Привет! Я Мария — фотограф и ретушёр 📸✨\nПодписывайтесь на мои соцсети, чтобы видеть свежие съёмки, портфолио и реальные "до/после" ретуши, а также быстро написать мне в личные сообщения.\n\nVK → https://vk.com/versavija\n\nInstagram → https://www.instagram.com/versavija?igsh=Y3ZhdnFvbWN0ejlq\n\nTikTok → https://www.tiktok.com/@00013_mariat_versavija?_t=ZS-8zC3OvSXSIZ&_r=1\n\nЖду ваши вопросы в директ — отвечаю лично 💬"""


def _admin_key_from_username(username: str | None) -> str:
    return (username or '').lstrip('@').lower()


def _load_reviews() -> list[str]:
    raw = get_setting('reviews_photos', '[]')
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


async def _show_reviews(message: Message, username: str, user_id: int) -> None:
    photos = _load_reviews()
    chat_key = (message.chat.id, 'reviews')
    displayed = False
    if photos:
        removed_invalid = False
        while photos:
            idx = len(photos) - 1
            fid = photos[idx]
            caption = f'⭐ Отзыв {idx + 1} из {len(photos)}'
            try:
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=fid,
                    caption=caption,
                    reply_markup=build_reviews_nav_keyboard(idx),
                )
                LAST_CATEGORY_PHOTO[chat_key] = idx
                displayed = True
                break
            except Exception as exc:
                logging.warning('Failed to send review photo idx=%s fid=%s: %s', idx, fid, exc)
                photos.pop(idx)
                removed_invalid = True
                set_setting('reviews_photos', json.dumps(photos, ensure_ascii=False))
                reset_last_category_position('reviews')
        if removed_invalid and not photos:
            await message.answer('⭐ Отзывы пока не добавлены.')
        elif not displayed:
            await message.answer('⭐ Отзывы пока не добавлены.')
    else:
        await message.answer('⭐ Отзывы пока не добавлены.')

    if await is_admin_view_enabled(username, user_id):
        await message.answer('Управление отзывами:', reply_markup=build_reviews_admin_keyboard())


def _get_social_text() -> str:
    return get_setting('social_media_text', _DEFAULT_SOCIAL_TEXT) or _DEFAULT_SOCIAL_TEXT


@content_router.message(Command(commands=['reviews']))
async def cmd_reviews(message: Message) -> None:
    username = _admin_key_from_username(message.from_user.username)
    await _show_reviews(message, username, message.from_user.id)


@content_router.message(Command(commands=['social']))
async def cmd_social(message: Message) -> None:
    username = _admin_key_from_username(message.from_user.username)
    await message.answer(_get_social_text())
    if await is_admin_view_enabled(username, message.from_user.id):
        await message.answer('Управление соцсетями:', reply_markup=build_social_admin_keyboard())


@content_router.callback_query(F.data == 'reviews')
async def cb_reviews(query: CallbackQuery) -> None:
    username = _admin_key_from_username(query.from_user.username)
    await _show_reviews(query.message, username, query.from_user.id)


@content_router.callback_query(F.data.startswith('reviews_pic:'))
async def cb_reviews_nav(query: CallbackQuery) -> None:
    photos = _load_reviews()
    if not photos:
        await query.message.answer('⭐ Отзывы пока не добавлены.')
        return

    chat_key = (query.message.chat.id, 'reviews')
    last_idx = LAST_CATEGORY_PHOTO.get(chat_key)
    if last_idx is None:
        idx = len(photos) - 1
    else:
        idx = last_idx - 1
        if idx < 0:
            idx = len(photos) - 1

    fid = photos[idx]
    caption = f'⭐ Отзыв {idx + 1} из {len(photos)}'
    try:
        await query.message.edit_media(InputMediaPhoto(media=fid, caption=caption))
        await query.message.edit_reply_markup(reply_markup=build_reviews_nav_keyboard(idx))
    except Exception:
        await bot.send_photo(
            chat_id=query.message.chat.id,
            photo=fid,
            caption=caption,
            reply_markup=build_reviews_nav_keyboard(idx),
        )
    LAST_CATEGORY_PHOTO[chat_key] = idx


@content_router.callback_query(F.data == 'reviews_add')
async def cb_reviews_add(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled(_admin_key_from_username(query.from_user.username), query.from_user.id):
        await query.message.answer('🚫 Нет доступа.')
        return
    admin_key = _admin_key_from_username(query.from_user.username)
    ADMIN_PENDING_ACTIONS.pop(admin_key, None)
    ADMIN_PENDING_ACTIONS[admin_key] = {'action': 'add_review', 'payload': {}}
    save_pending_actions(ADMIN_PENDING_ACTIONS)
    logging.info('Set pending action add_review for %s', admin_key)
    REVIEW_PENDING_USERS.add(query.from_user.id)
    await query.message.answer('📝 Отправьте фотографию отзыва:')


@content_router.callback_query(F.data == 'reviews_del')
async def cb_reviews_delete(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled(_admin_key_from_username(query.from_user.username), query.from_user.id):
        await query.message.answer('🚫 Нет доступа.')
        return
    photos = _load_reviews()
    if not photos:
        await query.message.answer('Нет отзывов для удаления.')
        return
    kb = build_reviews_delete_keyboard(photos)
    await query.message.answer(
        f"{MENU_MESSAGES['delete_review']} (всего: {len(photos)}):",
        reply_markup=kb,
    )


@content_router.callback_query(F.data.startswith('reviews_del_idx:'))
async def cb_reviews_delete_idx(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled(_admin_key_from_username(query.from_user.username), query.from_user.id):
        await query.message.answer('🚫 Нет доступа.')
        return
    parts = query.data.split(':', 1)
    if len(parts) < 2:
        return
    try:
        idx = int(parts[1])
    except ValueError:
        await query.message.answer('Неверный индекс отзыва.')
        return
    photos = _load_reviews()
    if not (0 <= idx < len(photos)):
        await query.message.answer('Неверный индекс отзыва.')
        return
    photos.pop(idx)
    set_setting('reviews_photos', json.dumps(photos, ensure_ascii=False))
    reset_last_category_position('reviews')
    await query.message.answer(f'✅ Отзыв #{idx + 1} удалён. Осталось: {len(photos)}')


@content_router.callback_query(F.data == 'social')
async def cb_social(query: CallbackQuery) -> None:
    username = _admin_key_from_username(query.from_user.username)
    await query.message.answer(_get_social_text())
    if await is_admin_view_enabled(username, query.from_user.id):
        await query.message.answer('Управление соцсетями:', reply_markup=build_social_admin_keyboard())


@content_router.callback_query(F.data == 'social_edit')
async def cb_social_edit(query: CallbackQuery) -> None:
    if not await is_admin_view_enabled(_admin_key_from_username(query.from_user.username), query.from_user.id):
        await query.message.answer('🚫 Нет доступа.')
        return
    admin_key = _admin_key_from_username(query.from_user.username)
    ADMIN_PENDING_ACTIONS[admin_key] = {'action': 'edit_social_text', 'payload': {}}
    save_pending_actions(ADMIN_PENDING_ACTIONS)
    await query.message.answer('📝 Отправьте новый текст для соцсетей:')


async def handle_content_pending_action(
    message: Message,
    username: str,
    action: str,
    payload: dict[str, Any],
) -> bool:
    if action == 'edit_social_text':
        if not message.text:
            await message.answer('Ожидаю текст для соцсетей. Попробуйте снова.')
            return True
        logging.info('Content pending: edit_social_text by %s', username)
        new_text = message.text.strip()
        if not new_text:
            await message.answer('Текст не может быть пустым.')
            ADMIN_PENDING_ACTIONS.pop(username, None)
            save_pending_actions(ADMIN_PENDING_ACTIONS)
            return True
        set_setting('social_media_text', new_text)
        ADMIN_PENDING_ACTIONS.pop(username, None)
        save_pending_actions(ADMIN_PENDING_ACTIONS)
        await message.answer('✅ Текст соцсетей обновлён.')
        return True

    if action == 'add_review':
        logging.info('Content pending: add_review by %s, has photo=%s', username, bool(message.photo))
        if message.photo:
            photos = _load_reviews()
            file_id = message.photo[-1].file_id
            if file_id not in photos:
                photos.append(file_id)
                set_setting('reviews_photos', json.dumps(photos, ensure_ascii=False))
                reset_last_category_position('reviews')
                logging.info('Review photo stored user=%s total=%s', message.from_user.id, len(photos))
                try:
                    await message.answer_photo(
                        file_id,
                        caption=f'⭐ Новый отзыв #{len(photos)} добавлен. Спасибо!',
                    )
                except Exception:
                    pass
                await message.answer(f'✅ Отзыв добавлен! Всего отзывов: {len(photos)}')
            else:
                await message.answer('Этот отзыв уже добавлен.')
            ADMIN_PENDING_ACTIONS.pop(username, None)
            save_pending_actions(ADMIN_PENDING_ACTIONS)
            REVIEW_PENDING_USERS.discard(message.from_user.id)
            return True
        await message.answer('Пожалуйста, отправьте фотографию отзыва.')
        REVIEW_PENDING_USERS.discard(message.from_user.id)
        return True

    return False


__all__ = [
    "content_router",
    "handle_content_pending_action",
]
