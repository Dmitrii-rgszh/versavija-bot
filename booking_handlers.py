from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db_async
from admin_utils import get_all_admin_ids, is_admin_view_enabled
from bot_constants import DEFAULT_MENU, MENU_MESSAGES
from config import DEFAULT_CITY_CENTER, DEFAULT_CITY_NAME, MAP_ZOOM_DEFAULT, bot
from keyboards import build_main_keyboard_from_menu
from utils import (
    fetch_yandex_address_from_html,
    fetch_yandex_coords_from_html,
    parse_plain_coords,
    parse_yandex_address_from_url,
    parse_yandex_coords,
    resolve_yandex_url,
    reverse_geocode_nominatim,
    yandex_link_for_city,
)

booking_router = Router(name="booking")
BOOKING_FLOW_MSGS: dict[int, list[int]] = {}
BOOK_TZ = timezone.utc

# --- Helpers -----------------------------------------------------------------


async def _build_loc_suffix(
    lat_val: float | None,
    lon_val: float | None,
    addr_val: str | None,
    src_val: str | None,
) -> str:
    try:
        if lat_val is None or lon_val is None:
            return ''
        url = f'https://yandex.ru/maps/?ll={float(lon_val):.6f},{float(lat_val):.6f}&z=16&pt={float(lon_val):.6f},{float(lat_val):.6f}'
        direct_addr = addr_val
        if not direct_addr and isinstance(src_val, str) and ('yandex.' in src_val or 'ya.ru' in src_val):
            try:
                resolved = await resolve_yandex_url(src_val)
                direct_addr = (
                    parse_yandex_address_from_url(resolved)
                    or await fetch_yandex_address_from_html(resolved)
                )
            except Exception:
                direct_addr = None
        if direct_addr:
            return f"\n📍 Локация: {url}\n🏷️ Адрес: {direct_addr}"
        return f"\n📍 Локация: {url}"
    except Exception:
        return ''


DEFAULT_PORTFOLIO_CATEGORIES = [
    {"text": "👨‍👩‍👧‍👦 Семейная", "slug": "family"},
    {"text": "💕 Love Story", "slug": "love_story"},
    {"text": "👤 Индивидуальная", "slug": "personal"},
    {"text": "🎉 Репортажная (банкеты, мероприятия)", "slug": "reportage"},
    {"text": "💍 Свадебная", "slug": "wedding"},
    {"text": "💋 Lingerie (будуарная)", "slug": "lingerie"},
    {"text": "👶 Детская (школы/садики)", "slug": "children"},
    {"text": "👩‍👶 Мама с ребёнком", "slug": "mom_child"},
    {"text": "✝️ Крещение", "slug": "baptism"},
    {"text": "⛪ Венчание", "slug": "wedding_church"},
]


async def get_portfolio_categories() -> list:
    raw = await db_async.get_setting('portfolio_categories', None)
    if raw:
        try:
            cats = json.loads(raw)
            if isinstance(cats, list) and cats:
                return cats
        except Exception:
            pass
    await db_async.set_setting('portfolio_categories', json.dumps(DEFAULT_PORTFOLIO_CATEGORIES, ensure_ascii=False))
    return DEFAULT_PORTFOLIO_CATEGORIES


async def _add_booking_status_user(user_id: int) -> None:
    raw = await db_async.get_setting('booking_status_user_ids', '') or ''
    parts = [p.strip() for p in raw.split(',') if p.strip()]
    if str(user_id) not in parts:
        parts.append(str(user_id))
        await db_async.set_setting('booking_status_user_ids', ','.join(parts))


async def inject_booking_status_button(kb: InlineKeyboardMarkup, user_id: int) -> InlineKeyboardMarkup:
    booking = await db_async.get_active_booking_for_user(user_id)
    if not booking:
        return kb
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


async def _send_booking_step(
    q: CallbackQuery,
    text: str,
    kb: Optional[InlineKeyboardMarkup] = None,
) -> Message:
    chat_id = q.message.chat.id
    tracked = BOOKING_FLOW_MSGS.get(chat_id, [])

    # Case 1: edit existing booking message
    if tracked and q.message and q.message.message_id in tracked:
        old_text = q.message.text or ''
        animate = old_text != text
        try:
            if animate:
                dots = ['·', '•', '∙', '⋅', '∘', '⁘', '⁙', '⁚', '﹒']

                def replace_portion(src: str, portion: float) -> str:
                    if not src:
                        return ''
                    idxs = list(range(len(src)))
                    random.shuffle(idxs)
                    cut = int(len(src) * portion)
                    repl_set = set(idxs[:cut])
                    out = []
                    alt = 0
                    for i, ch in enumerate(src):
                        if i in repl_set and not ch.isspace():
                            out.append(dots[alt % len(dots)])
                            alt += 1
                        else:
                            out.append(ch)
                    return ''.join(out)

                frames = [
                    replace_portion(old_text, 0.3),
                    replace_portion(old_text, 0.7),
                    ''.join('·' if not ch.isspace() else ch for ch in old_text),
                    ' '.join('·' for _ in range(max(1, len(old_text) // 4)))
                ]
                for frame in frames:
                    try:
                        await q.message.edit_text(frame)
                    except Exception:
                        break
                    await asyncio.sleep(0.05)
            await q.message.edit_text(text, reply_markup=kb)
            return q.message
        except Exception:
            logging.exception('Failed to edit booking step message')

    # Case 2: send new message
    try:
        for mid in BOOKING_FLOW_MSGS.get(chat_id, []):
            try:
                await bot.delete_message(chat_id, mid)
            except Exception:
                pass
        m = await q.message.answer(text, reply_markup=kb)
        BOOKING_FLOW_MSGS[chat_id] = [m.message_id]
        return m
    except Exception:
        logging.exception('Failed to send booking step message')
        return q.message


def build_booking_date_kb() -> InlineKeyboardMarkup:
    today = datetime.now(BOOK_TZ).date()
    dates = [today + timedelta(days=i) for i in range(1, 31)]
    rows = []
    row = []
    for d in dates:
        row.append(InlineKeyboardButton(text=d.strftime('%d.%m'), callback_data=f'bk_d:{d.isoformat()}'))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text='❌ Отмена', callback_data='bk_cancel')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def build_booking_hours_kb(date_iso: str) -> InlineKeyboardMarkup:
    start = datetime.fromisoformat(date_iso).replace(tzinfo=BOOK_TZ)
    end = start + timedelta(days=1)
    bookings = await db_async.get_bookings_between(start.isoformat(), end.isoformat())
    taken = set()
    for b in bookings:
        try:
            h = datetime.fromisoformat(b['start_ts']).hour
        except Exception:
            continue
        taken.add(h)
        if h + 1 < 24:
            taken.add(h + 1)
    hours = list(range(18, 22)) if start.weekday() < 5 else list(range(10, 22))
    rows = []
    row = []
    for h in hours:
        busy = h in taken
        cb = 'bk_h_taken' if busy else f'bk_h:{date_iso}:{h}'
        row.append(InlineKeyboardButton(text=f'{h:02d}:00' + (' ⛔' if busy else ''), callback_data=cb))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data='bk_back_date')])
    rows.append([InlineKeyboardButton(text='❌ Отмена', callback_data='bk_cancel')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_booking_confirm_kb(date_iso: str, hour: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Подтвердить', callback_data=f'bk_cf:{date_iso}:{hour}')],
        [InlineKeyboardButton(text='↩️ Изменить', callback_data='bk_back_date')],
        [InlineKeyboardButton(text='❌ Отмена', callback_data='bk_cancel')],
    ])


def build_booking_loc_kb(date_iso: str, hour: int, slug: str) -> InlineKeyboardMarkup:
    city_lat, city_lon = DEFAULT_CITY_CENTER
    url = yandex_link_for_city(city_lat, city_lon, DEFAULT_CITY_NAME, MAP_ZOOM_DEFAULT)
    rows = [
        [InlineKeyboardButton(text='🗺️ Открыть Яндекс.Карты', url=url)],
        [InlineKeyboardButton(text='⏭️ Пропустить локацию', callback_data=f'bk_loc_skip:{date_iso}:{hour}:{slug}')],
        [InlineKeyboardButton(text='⬅️ Назад', callback_data='bk_back_date')],
        [InlineKeyboardButton(text='❌ Отмена', callback_data='bk_cancel')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --- Message handlers --------------------------------------------------------

@booking_router.message(Command(commands=['booking']))
async def cmd_booking(message: Message) -> None:
    user_id = message.from_user.id
    bk = await db_async.get_active_booking_for_user(user_id)
    if bk:
        dt = datetime.fromisoformat(bk['start_ts'])
        txt = (
            '📅 Ваша запись:\n'
            f'Время: {dt.strftime("%H:%M %d.%m.%Y")}\n'
            f'Категория: {bk.get("category") or "—"}'
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Перенести', callback_data=f'bk_resch:{bk["id"]}')],
            [InlineKeyboardButton(text='Отменить', callback_data=f'bk_cancel_booking:{bk["id"]}')],
            [InlineKeyboardButton(text='⬅️ В меню', callback_data='back_main')],
        ])
        await message.answer(txt, reply_markup=kb)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📅 Записаться', callback_data='booking')],
        [InlineKeyboardButton(text='⬅️ В меню', callback_data='back_main')],
    ])
    await message.answer('📅 Запись на фотосессию', reply_markup=kb)


@booking_router.message()
async def catch_yandex_link(message: Message) -> None:
    text = (message.text or '').strip()
    if not text and not getattr(message, 'location', None):
        return
    pend_raw = await db_async.get_setting(f'pending_booking_{message.from_user.id}', None)
    if not pend_raw:
        return
    try:
        pend = json.loads(pend_raw)
    except Exception:
        return
    if not pend.get('await_loc'):
        return

    logging.info(
        'Booking location message user=%s await_loc=%s text_present=%s location_present=%s',
        message.from_user.id,
        True,
        bool(text),
        bool(getattr(message, 'location', None)),
    )

    # Native Telegram location
    if getattr(message, 'location', None):
        loc = message.location
        lat = float(loc.latitude)
        lon = float(loc.longitude)
        pend['loc_lat'] = lat
        pend['loc_lon'] = lon
        pend['loc_text'] = f'Telegram geo: {lat:.6f},{lon:.6f}'
        pend['loc_source'] = 'telegram_location'
        pend['await_loc'] = False
        await db_async.set_setting(f'pending_booking_{message.from_user.id}', json.dumps(pend, ensure_ascii=False))
        try:
            date_iso = pend.get('date')
            hour = pend.get('hour')
            slug = pend.get('slug')
            start_dt = datetime.fromisoformat(date_iso).replace(
                tzinfo=BOOK_TZ, hour=int(hour), minute=0, second=0, microsecond=0
            )
            cats = await get_portfolio_categories()
            cat = next((c for c in cats if c.get('slug') == slug), {'text': slug})
            human = start_dt.strftime('%d.%m.%Y %H:%M')
            addr_line = ''
            if pend.get('loc_addr'):
                addr_line = f"\nАдрес: {pend.get('loc_addr')}"
            kb = build_booking_confirm_kb(date_iso, hour)
            logging.info('Booking location accepted (telegram) user=%s slug=%s coords=(%s,%s)', message.from_user.id, slug, lat, lon)
            await message.answer(
                f'📍 Локация принята{addr_line}\n\nВы выбрали {human}\nКатегория: {cat.get("text")}\nПодтвердить?',
                reply_markup=kb,
            )
        except Exception:
            await message.answer('📍 Локация принята. Нажмите Подтвердить на предыдущем шаге.')
        return

    # Links/text with coordinates
    if not text:
        return
    coords = parse_yandex_coords(text)
    url_addr = parse_yandex_address_from_url(text) if ('yandex.' in text or 'ya.ru' in text) else None
    if not coords and ('yandex.' in text or 'ya.ru' in text):
        try:
            resolved = await resolve_yandex_url(text)
            if not resolved or resolved == text:
                logging.warning('Resolve returned same URL user=%s text=%s', message.from_user.id, text)
            coords = parse_yandex_coords(resolved)
            if not url_addr:
                url_addr = parse_yandex_address_from_url(resolved)
            if not coords:
                coords = await fetch_yandex_coords_from_html(resolved)
            if not url_addr:
                url_addr = await fetch_yandex_address_from_html(resolved)
            logging.info('Resolved yandex link user=%s original=%s resolved=%s coords=%s addr=%s',
                         message.from_user.id, text, resolved, coords, url_addr)
        except Exception as exc:
            logging.warning('Failed to resolve yandex link user=%s text=%s err=%s', message.from_user.id, text, exc)
            coords = None
    if not coords:
        coords = parse_plain_coords(text)
    if not coords:
        if 'yandex.' in text or 'ya.ru' in text:
            try:
                await message.answer(
                    '⚠️ Не удалось распознать координаты. Варианты:\n'
                    '• Откройте ссылку → Поделиться → Скопировать ссылку (чтобы были ll= или pt=)\n'
                    '• Отправьте геолокацию через «📎»\n'
                    '• Пришлите "lat, lon", например: 53.252560, 50.249664\n'
                    '• Или нажмите «Пропустить локацию».',
                )
            except Exception:
                pass
        raise SkipHandler()
    lat, lon = coords
    addr_value = url_addr
    logging.info(
        'Booking location parsed user=%s coords=(%s,%s) addr=%s',
        message.from_user.id,
        lat,
        lon,
        addr_value,
    )
    if not addr_value or not any(ch.isdigit() for ch in addr_value):
        try:
            rev_addr = await reverse_geocode_nominatim(lat, lon)
        except Exception:
            rev_addr = None
        if rev_addr:
            addr_value = rev_addr

    pend['loc_lat'] = lat
    pend['loc_lon'] = lon
    pend['loc_text'] = f'Яндекс.Карты: {lat:.6f},{lon:.6f}'
    if addr_value:
        pend['loc_addr'] = addr_value
    pend['loc_source'] = text
    pend['await_loc'] = False
    await db_async.set_setting(f'pending_booking_{message.from_user.id}', json.dumps(pend, ensure_ascii=False))
    try:
        date_iso = pend.get('date')
        hour = pend.get('hour')
        slug = pend.get('slug')
        start_dt = datetime.fromisoformat(date_iso).replace(
            tzinfo=BOOK_TZ, hour=int(hour), minute=0, second=0, microsecond=0
        )
        cats = await get_portfolio_categories()
        cat = next((c for c in cats if c.get('slug') == slug), {'text': slug})
        human = start_dt.strftime('%d.%m.%Y %H:%M')
        addr_line = ''
        if pend.get('loc_addr'):
            addr_line = f"\nАдрес: {pend.get('loc_addr')}"
        kb = build_booking_confirm_kb(date_iso, hour)
        logging.info('Booking location accepted (link) user=%s slug=%s coords=(%s,%s)', message.from_user.id, slug, lat, lon)
        await message.answer(
            f'📍 Локация принята{addr_line}\n\nВы выбрали {human}\nКатегория: {cat.get("text")}',
            reply_markup=kb,
        )
    except Exception:
        await message.answer('📍 Локация принята. Нажмите Подтвердить на предыдущем шаге.')
    return


# --- Callback handlers -------------------------------------------------------

@booking_router.callback_query(F.data == 'booking')
async def start_booking_flow(query: CallbackQuery) -> None:
    await db_async.set_setting(f'resched_{query.from_user.id}', '')
    BOOKING_FLOW_MSGS[query.message.chat.id] = []
    await _send_booking_step(query, 'Выберите дату:', build_booking_date_kb())


@booking_router.callback_query(F.data == 'bk_cancel')
async def cancel_booking_flow(query: CallbackQuery) -> None:
    await _send_booking_step(query, 'Запись отменена.')
    BOOKING_FLOW_MSGS[query.message.chat.id] = []
    await db_async.set_setting(f'pending_booking_{query.from_user.id}', '')


@booking_router.callback_query(F.data == 'bk_back_date')
async def booking_back_to_date(query: CallbackQuery) -> None:
    await _send_booking_step(query, 'Выберите дату:', build_booking_date_kb())


@booking_router.callback_query(F.data.startswith('bk_d:'))
async def booking_pick_date(query: CallbackQuery) -> None:
    _, date_iso = query.data.split(':', 1)
    target = datetime.fromisoformat(date_iso).strftime('%d.%m.%Y')
    kb = await build_booking_hours_kb(date_iso)
    await _send_booking_step(query, f'Дата {target}. Выберите время:', kb)


@booking_router.callback_query(F.data == 'bk_h_taken')
async def booking_hour_taken(query: CallbackQuery) -> None:
    await query.answer('Слот занят')


@booking_router.callback_query(F.data.startswith('bk_h:'))
async def booking_pick_hour(query: CallbackQuery) -> None:
    _, date_iso, hour = query.data.split(':', 2)
    hour = int(hour)
    start_dt = datetime.fromisoformat(date_iso).replace(
        tzinfo=BOOK_TZ, hour=hour, minute=0, second=0, microsecond=0
    )
    buffer_dt = start_dt + timedelta(hours=1)
    prev_dt = start_dt - timedelta(hours=1)
    if (
        await db_async.is_slot_taken(start_dt.isoformat())
        or await db_async.is_slot_taken(buffer_dt.isoformat())
        or await db_async.is_slot_taken(prev_dt.isoformat())
    ):
        await query.answer('Слот занят')
        return
    cats = await get_portfolio_categories()
    rows = []
    row = []
    for c in cats:
        row.append(
            InlineKeyboardButton(text=c.get('text'), callback_data=f'bk_cat:{date_iso}:{hour}:{c.get("slug")}')
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data='bk_back_date')])
    rows.append([InlineKeyboardButton(text='❌ Отмена', callback_data='bk_cancel')])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await _send_booking_step(query, MENU_MESSAGES['booking'], kb)


@booking_router.callback_query(F.data.startswith('bk_cat:'))
async def booking_pick_category(query: CallbackQuery) -> None:
    _, date_iso, hour, slug = query.data.split(':', 3)
    hour = int(hour)
    start_dt = datetime.fromisoformat(date_iso).replace(
        tzinfo=BOOK_TZ, hour=hour, minute=0, second=0, microsecond=0
    )
    buffer_dt = start_dt + timedelta(hours=1)
    prev_dt = start_dt - timedelta(hours=1)
    if (
        await db_async.is_slot_taken(start_dt.isoformat())
        or await db_async.is_slot_taken(buffer_dt.isoformat())
        or await db_async.is_slot_taken(prev_dt.isoformat())
    ):
        await query.answer('Слот занят')
        return
    await db_async.set_setting(
        f'pending_booking_{query.from_user.id}',
        json.dumps({'date': date_iso, 'hour': hour, 'slug': slug, 'await_loc': True}, ensure_ascii=False),
    )
    cats = await get_portfolio_categories()
    cat = next((c for c in cats if c.get('slug') == slug), {'text': slug})
    human = start_dt.strftime('%d.%m.%Y %H:%M')
    text = (
        f'Вы выбрали {human}\nКатегория: {cat.get("text")}\n\n'
        '📍 Локация съёмки:\n'
        f'Откройте Яндекс.Карты по кнопке ниже (по умолчанию — {DEFAULT_CITY_NAME}),\n'
        'выберите место → Поделиться → Скопировать ссылку и пришлите её сюда одним сообщением.'
    )
    kb = build_booking_loc_kb(date_iso, hour, slug)
    await _send_booking_step(query, text, kb)


@booking_router.callback_query(F.data.startswith('bk_loc_skip:'))
async def booking_skip_location(query: CallbackQuery) -> None:
    _, date_iso, hour, slug = query.data.split(':', 3)
    hour = int(hour)
    pend_raw = await db_async.get_setting(f'pending_booking_{query.from_user.id}', None)
    pend = {}
    if pend_raw:
        try:
            pend = json.loads(pend_raw)
        except Exception:
            pend = {}
    pend['await_loc'] = False
    await db_async.set_setting(f'pending_booking_{query.from_user.id}', json.dumps(pend, ensure_ascii=False))
    start_dt = datetime.fromisoformat(date_iso).replace(
        tzinfo=BOOK_TZ, hour=hour, minute=0, second=0, microsecond=0
    )
    cats = await get_portfolio_categories()
    cat = next((c for c in cats if c.get('slug') == slug), {'text': slug})
    human = start_dt.strftime('%d.%m.%Y %H:%M')
    addr_line = ''
    if pend.get('loc_addr'):
        addr_line = f"\nАдрес: {pend.get('loc_addr')}"
    kb = build_booking_confirm_kb(date_iso, hour)
    await _send_booking_step(query, f'Вы выбрали {human}\nКатегория: {cat.get("text")}\nПодтвердить?{addr_line}', kb)


@booking_router.callback_query(F.data.startswith('bk_cf:'))
async def booking_confirm(query: CallbackQuery) -> None:
    _, date_iso, hour = query.data.split(':', 2)
    hour = int(hour)
    start_dt = datetime.fromisoformat(date_iso).replace(
        tzinfo=BOOK_TZ, hour=hour, minute=0, second=0, microsecond=0
    )
    buffer_dt = start_dt + timedelta(hours=1)
    prev_dt = start_dt - timedelta(hours=1)
    if (
        await db_async.is_slot_taken(start_dt.isoformat())
        or await db_async.is_slot_taken(buffer_dt.isoformat())
        or await db_async.is_slot_taken(prev_dt.isoformat())
    ):
        await query.message.answer('Слот уже занят, начните заново.')
        return

    pending_raw = await db_async.get_setting(f'pending_booking_{query.from_user.id}', None)
    pend = {}
    slug = None
    if pending_raw:
        try:
            pend = json.loads(pending_raw)
            slug = pend.get('slug')
        except Exception:
            pend = {}
            slug = None
    if not slug:
        await query.message.answer('Категория утрачена, начните заново.')
        await query.message.answer(MENU_MESSAGES['select_date'], reply_markup=build_booking_date_kb())
        return

    cats = await get_portfolio_categories()
    cat = next((c for c in cats if c.get('slug') == slug), {'text': slug})
    res_raw = await db_async.get_setting(f'resched_{query.from_user.id}', None)
    try:
        res_info = json.loads(res_raw) if res_raw else {}
    except Exception:
        res_info = {}

    if res_info.get('bid'):
        old_bk = await db_async.get_booking(res_info['bid'])
        if old_bk and old_bk['user_id'] == query.from_user.id and old_bk['status'] in ('active', 'confirmed'):
            old_start = old_bk['start_ts']
            if pend.get('loc_lat') is not None and pend.get('loc_lon') is not None:
                await db_async.update_booking_time_category_location(
                    res_info['bid'],
                    start_dt.isoformat(),
                    cat.get('text'),
                    pend.get('loc_lat'),
                    pend.get('loc_lon'),
                    pend.get('loc_text'),
                    pend.get('loc_source'),
                    pend.get('loc_addr'),
                )
            else:
                await db_async.update_booking_time_and_category(res_info['bid'], start_dt.isoformat(), cat.get('text'))

            await _send_booking_step(query, f'🔁 Запись обновлена: {start_dt.strftime("%d.%m.%Y %H:%M")}')
            old_h = datetime.fromisoformat(old_start).strftime('%H:%M %d.%m.%Y')
            new_h = start_dt.strftime('%H:%M %d.%m.%Y')
            loc_suffix = await _build_loc_suffix(
                pend.get('loc_lat'), pend.get('loc_lon'), pend.get('loc_addr'), pend.get('loc_source')
            )
            for aid in await get_all_admin_ids():
                try:
                    await bot.send_message(
                        aid,
                        f'🔁 Пользователь @{(query.from_user.username or "(нет)").lower()} перенёс запись: '
                        f'{old_h} -> {new_h}. Категория: "{cat.get("text")}"{loc_suffix}'
                    )
                except Exception:
                    pass
            await _add_booking_status_user(query.from_user.id)
        else:
            await query.message.answer('Исходная запись не найдена, создана новая.')
            await db_async.add_booking(
                query.from_user.id,
                query.from_user.username,
                query.message.chat.id,
                start_dt.isoformat(),
                cat.get('text'),
                pend.get('loc_lat'),
                pend.get('loc_lon'),
                pend.get('loc_text'),
                pend.get('loc_source'),
                pend.get('loc_addr'),
            )
            await _add_booking_status_user(query.from_user.id)
        await db_async.set_setting(f'resched_{query.from_user.id}', '')
    else:
        await db_async.add_booking(
            query.from_user.id,
            query.from_user.username,
            query.message.chat.id,
            start_dt.isoformat(),
            cat.get('text'),
            pend.get('loc_lat'),
            pend.get('loc_lon'),
            pend.get('loc_text'),
            pend.get('loc_source'),
            pend.get('loc_addr'),
        )
        await _send_booking_step(
            query,
            f'✅ Запись создана: {start_dt.strftime("%d.%m.%Y %H:%M")} (с резервом до {buffer_dt.strftime("%H:%M")}). '
            'Напоминание за 24 часа.',
        )
        loc_suffix = await _build_loc_suffix(
            pend.get('loc_lat'), pend.get('loc_lon'), pend.get('loc_addr'), pend.get('loc_source')
        )
        for aid in await get_all_admin_ids():
            try:
                await bot.send_message(
                    aid,
                    f'🆕 Добавлена запись @{(query.from_user.username or "(нет)").lower()}: '
                    f'{start_dt.strftime("%H:%M %d.%m.%Y")} Категория: "{cat.get("text")}"{loc_suffix}'
                )
            except Exception:
                pass
        await _add_booking_status_user(query.from_user.id)

    await db_async.set_setting(f'pending_booking_{query.from_user.id}', '')
    menu = await db_async.get_menu(DEFAULT_MENU)
    kb_main = build_main_keyboard_from_menu(menu, await is_admin_view_enabled((query.from_user.username or '').lstrip('@').lower(), query.from_user.id))
    kb_main = await inject_booking_status_button(kb_main, query.from_user.id)
    await bot.send_message(query.message.chat.id, MENU_MESSAGES['main'], reply_markup=kb_main)


@booking_router.callback_query(F.data == 'bk_resch')
async def ignore_resch(query: CallbackQuery) -> None:
    await query.answer()


@booking_router.callback_query(F.data.startswith('bk_resch:'))
async def booking_reschedule(query: CallbackQuery) -> None:
    _, bid_str = query.data.split(':', 1)
    try:
        bid = int(bid_str)
    except ValueError:
        return
    bk = await db_async.get_booking(bid)
    if not bk or bk['user_id'] != query.from_user.id or bk['status'] not in ('active', 'confirmed'):
        await query.message.answer('Невозможно перенести: запись не найдена.')
        return
    await db_async.set_setting(f'resched_{query.from_user.id}', json.dumps({'bid': bid, 'old_start': bk['start_ts']}, ensure_ascii=False))
    BOOKING_FLOW_MSGS[query.message.chat.id] = []
    await _send_booking_step(query, 'Выберите дату:', build_booking_date_kb())


@booking_router.callback_query(F.data.startswith('bk_cancel_booking:'))
async def booking_cancel_existing(query: CallbackQuery) -> None:
    _, bid_str = query.data.split(':', 1)
    try:
        bid = int(bid_str)
    except ValueError:
        return
    bk = await db_async.get_booking(bid)
    if not bk or bk['user_id'] != query.from_user.id or bk['status'] not in ('active', 'confirmed'):
        await query.message.answer('Невозможно отменить: запись не найдена.')
        return
    await db_async.update_booking_status(bid, 'cancelled')
    try:
        dt_old = datetime.fromisoformat(bk['start_ts']).strftime('%H:%M %d.%m.%Y')
    except Exception:
        dt_old = bk['start_ts']
    for aid in await get_all_admin_ids():
        try:
            await bot.send_message(
                aid,
                f'❌ Пользователь @{(query.from_user.username or "(нет)").lower()} отменил запись на {dt_old}.',
            )
        except Exception:
            pass
    menu = await db_async.get_menu(DEFAULT_MENU)
    kb = build_main_keyboard_from_menu(menu, await is_admin_view_enabled((query.from_user.username or '').lstrip('@').lower(), query.from_user.id))
    kb = await inject_booking_status_button(kb, query.from_user.id)
    await query.message.answer(MENU_MESSAGES['main'], reply_markup=kb)


@booking_router.callback_query(F.data == 'booking_status')
async def booking_status_card(query: CallbackQuery) -> None:
    bk = await db_async.get_active_booking_for_user(query.from_user.id)
    if not bk:
        menu = await db_async.get_menu(DEFAULT_MENU)
        kb = build_main_keyboard_from_menu(menu, await is_admin_view_enabled((query.from_user.username or '').lstrip('@').lower(), query.from_user.id))
        kb = await inject_booking_status_button(kb, query.from_user.id)
        await query.message.answer(MENU_MESSAGES['main'], reply_markup=kb)
        return
    dt = datetime.fromisoformat(bk['start_ts'])
    loc_suffix = await _build_loc_suffix(
        bk.get('loc_lat'),
        bk.get('loc_lon'),
        bk.get('loc_addr'),
        bk.get('loc_source'),
    )
    extra_loc = ''
    if not loc_suffix and bk.get('loc_text'):
        extra_loc = f"\n📍 Локация: {bk.get('loc_text')}"
    txt = (
        '📅 Ваша запись:\n'
        f'Время: {dt.strftime("%H:%M %d.%м.%Y")}\n'
        f'Категория: {bk.get("category") or "—"}'
    )
    if loc_suffix:
        txt += loc_suffix
    elif extra_loc:
        txt += extra_loc
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Перенести', callback_data=f'bk_resch:{bk["id"]}')],
        [InlineKeyboardButton(text='Отменить', callback_data=f'bk_cancel_booking:{bk["id"]}')],
        [InlineKeyboardButton(text='⬅️ В меню', callback_data='back_main')],
    ])
    await query.message.answer(txt, reply_markup=kb)
