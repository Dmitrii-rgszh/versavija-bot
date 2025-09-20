import asyncio
import logging
import sqlite3
import json
from pathlib import Path
from datetime import datetime, date, timedelta
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from config import bot
from db import get_setting, set_setting
from urllib.parse import quote_plus, urlencode
from aiogram.types import FSInputFile
import random
import urllib.request
import urllib.error
import tempfile
import mimetypes
import hashlib

# Канал для поздравлений (используем тот же, что и для приветствий)
BIRTHDAY_CHANNEL_ID = -1002553563891


def _load_birthday_messages() -> list[str]:
    path = Path(__file__).parent / 'media' / 'birthday_messages.json'
    default: list[str] = [
        "🎂 {mention}, с Днём Рождения! Пусть каждый кадр жизни будет ярким и тёплым! 📸✨",
        "🎉 Ура, {mention}! Желаю вдохновения, радости и волшебных моментов каждый день! ✨",
        "🌟 {mention}, пусть счастье светит как софиты, а мечты исполняются в фокусе! 💫",
        "💐 С праздником, {mention}! Пусть жизнь будет как серия лучших снимков — только удачные кадры! 📷",
        "🎈 {mention}, лёгкости, улыбок и уютных историй в этом новом году жизни! 😊",
        "🍰 {mention}, пусть каждый новый день будет красивее предыдущего! С Днём Рождения!",
        "💖 Счастья тебе, {mention}! Тепла, любви и нежных моментов, которые хочется хранить в альбоме!",
        "🌼 {mention}, пусть вокруг всегда будет свет, вдохновение и любимые люди рядом!",
        "✨ {mention}, желаю волшебства в мелочах и больших побед! С праздником!",
        "🎁 {mention}, пусть подарков будет много, а эмоции — самые искренние!",
        "🌈 {mention}, больше ярких красок, новых идей и приятных сюрпризов!",
        "📸 {mention}, пусть каждый день будет поводом для красивого кадра и улыбки!",
        "💫 {mention}, пусть вселенная бережно исполняет твои желания — одно за другим!",
        "🌷 {mention}, гармонии, уюта и самых тёплых объятий в этот день!",
        "🎊 {mention}, пусть праздник длится дольше, а радость — ещё дольше!",
        "🕊️ {mention}, лёгкости в сердце, ясного неба и вдохновения на новые свершения!",
        "🥳 {mention}, пусть этот год будет щедрым на чудеса и приятные открытия!",
        "🌟 {mention}, твори, мечтай, сияй! Мы рядом и радуемся вместе с тобой!",
        "🍓 {mention}, сладких моментов, уютных встреч и теплых воспоминаний!",
        "🌻 {mention}, солнечного настроения, искренних улыбок и душевной гармонии!",
        "🎶 {mention}, пусть жизнь звучит любимой мелодией и радует каждый день!",
        "🧁 {mention}, нежности, заботы и много вкусных маленьких радостей!",
        "💎 {mention}, сияй ярко! Ты — настоящая жемчужина этого дня!",
        "🌙 {mention}, пусть мечты сбываются легко и красиво — как в кино!",
        "📷 {mention}, пусть твой мир будет всегда в идеальном свете и с правильным настроением!"
    ]
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list) and all(isinstance(x, str) for x in data) and len(data) >= 10:
            return data
    except FileNotFoundError:
        pass
    except Exception as e:
        logging.warning('Не удалось загрузить birthday_messages.json: %s, используем встроенные', e)
    return default


BIRTHDAY_MESSAGES = _load_birthday_messages()


def _parse_birth_mmdd(birthdate: str | None) -> tuple[int, int] | None:
    if not birthdate:
        return None
    try:
        parts = birthdate.split('-')
        if len(parts) == 3:
            y, m, d = parts
            return (int(m), int(d))
        if len(parts) == 2:
            m, d = parts
            return (int(m), int(d))
    except Exception:
        return None
    return None


def _mention(username: str | None, user_id: int, first_name: str | None, last_name: str | None) -> str:
    # Без форматирования Markdown/HTML, чтобы не падать на подчёркиваниях в @username
    if username:
        return f"@{username}"
    name = (first_name or '').strip()
    if last_name:
        name = (name + ' ' + last_name).strip()
    return name or 'друг'


def _next_birthday_from(mm: int, dd: int, today: date) -> date:
    year = today.year
    try:
        cand = date(year, mm, dd)
    except ValueError:
        # На случай 29 февраля (используем 28 в невисокосный)
        if mm == 2 and dd == 29:
            cand = date(year, 2, 28)
        else:
            raise
    if cand < today:
        try:
            cand = date(year + 1, mm, dd)
        except ValueError:
            if mm == 2 and dd == 29:
                cand = date(year + 1, 2, 28)
    return cand


def random_choice(lst: list[str]) -> str:
    import random
    return random.choice(lst) if lst else ''


def _get_setting_bool(key: str, default: bool = False) -> bool:
    val = (get_setting(key, None) or ('on' if default else 'off')).strip().lower()
    return val in ('1', 'true', 'on', 'yes')


def _has_human_indicator(title: str, categories: list[str]) -> bool:
    t = (title or '').lower()
    bad_tokens = (
        'people', 'person', 'human', 'men', 'women', 'man', 'woman', 'boy', 'girl', 'child', 'children',
        'portrait', 'self-portrait', 'wedding', 'bride', 'groom', 'couple', 'festival', 'crowd', 'family'
    )
    if any(bt in t for bt in bad_tokens):
        return True
    clower = [c.lower() for c in categories]
    bad_cats = (
        'people', 'humans', 'men', 'women', 'portraits', 'weddings', 'bride', 'groom', 'couples', 'children'
    )
    return any(any(bc in c for bc in bad_cats) for c in clower)


def _has_wilted_indicator(title: str, categories: list[str]) -> bool:
    t = (title or '').lower()
    bad_tokens = (
        'wilt', 'wilted', 'wither', 'withered', 'dried', 'dry flower', 'dry flowers', 'herbarium',
        'pressed flower', 'dead flower', 'faded', 'fade', 'decay'
    )
    if any(bt in t for bt in bad_tokens):
        return True
    clower = [c.lower() for c in categories]
    bad_cats = (
        'dried', 'herbarium', 'pressed flowers', 'dried flowers', 'wilted'
    )
    return any(any(bc in c for bc in bad_cats) for c in clower)


def _looks_like_flowers_query(query: str) -> bool:
    q = (query or '').lower()
    tokens = ('flower', 'flowers', 'floral', 'bouquet', 'rose', 'roses', 'tulip', 'tulips', 'peony', 'peonies')
    return any(t in q for t in tokens)


def _looks_like_bouquet_query(query: str) -> bool:
    q = (query or '').lower()
    tokens = ('bouquet', 'bouquets', 'arrangement', 'arrangements', 'floristry', 'vase')
    return any(t in q for t in tokens)


def _score_flower_candidate(title: str, categories: list[str]) -> int:
    t = (title or '').lower()
    cats = ' '.join([c.lower() for c in categories])
    good = (
        'bouquet', 'bouquets', 'wedding', 'bridal', 'arrangement', 'arrangements', 'florist', 'floristry',
        'peony', 'peonies', 'rose', 'roses', 'ranunculus', 'hydrangea', 'orchid', 'tulip', 'tulips', 'lily', 'lilies',
        'premium', 'luxury', 'large', 'many flowers'
    )
    bad = (
        'vase', 'still life', 'still-life', 'table', 'minimal', 'single', 'one flower', 'wildflower', 'wildflowers',
        'daisy', 'daisies'
    )
    score = 0
    score += sum(2 for g in good if g in t) + sum(1 for g in good if g in cats)
    score -= sum(2 for b in bad if b in t) + sum(1 for b in bad if b in cats)
    return score


def _build_random_image_urls() -> list[str]:
    if not _get_setting_bool('birthday_image_enabled', False):
        return []
    provider = (get_setting('birthday_image_provider', 'loremflickr') or 'loremflickr').strip().lower()
    query = (get_setting('birthday_image_query', 'birthday,balloons,cake,party') or 'birthday,balloons,cake,party').strip()
    q = quote_plus(query)
    urls: list[str] = []
    avoid_picsum = _looks_like_flowers_query(query)
    strict = _get_setting_bool('birthday_image_flowers_strict', True)
    luxury_terms = 'luxury,premium,wedding,bridal,florist,arrangement,roses,peonies,ranunculus,hydrangea,orchids,bouquet'
    if provider == 'static':
        url = (get_setting('birthday_image_static_url', '') or '').strip()
        if url:
            urls.append(url)
        return urls
    if provider == 'unsplash_source':
        if _looks_like_bouquet_query(query):
            q2 = quote_plus(query + ',' + luxury_terms)
        else:
            q2 = quote_plus(query + ',closeup,macro')
        urls.append(f"https://source.unsplash.com/random/1200x800/?{q2}")
        if not strict:
            urls.append(f"https://loremflickr.com/1200/800/{q}")
    elif provider == 'loremflickr':
        if not strict:
            urls.append(f"https://loremflickr.com/1200/800/{q}")
            urls.append(f"https://source.unsplash.com/random/1200x800/?{q}")
    elif provider == 'picsum':
        if not strict and not avoid_picsum:
            urls.append("https://picsum.photos/1200/800")
    else:
        if strict:
            if _looks_like_bouquet_query(query):
                q2 = quote_plus(query + ',' + luxury_terms)
            else:
                q2 = quote_plus(query + ',closeup,macro')
            urls.append(f"https://source.unsplash.com/random/1200x800/?{q2}")
        else:
            urls.append(f"https://loremflickr.com/1200/800/{q}")
            urls.append(f"https://source.unsplash.com/random/1200x800/?{q}")
            if not avoid_picsum:
                urls.append("https://picsum.photos/1200/800")
    return urls


def _download_image_to_temp(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'versavija-bot/1.0 (+https://t.me/versavija)',
            'Accept': 'image/*,*/*;q=0.8'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get('Content-Type', '').lower()
            if 'image' not in content_type:
                return None
            data = resp.read()
            ext = mimetypes.guess_extension(content_type.split(';')[0]) or '.jpg'
            fd, path = tempfile.mkstemp(prefix='bd_', suffix=ext)
            with open(fd, 'wb') as f:
                f.write(data)
            return path
    except Exception as e:
        logging.info('Ошибка скачивания изображения %s: %s', url, e)
        return None


def _download_image_with_fingerprint(url: str) -> tuple[str | None, str | None]:
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'versavija-bot/1.0 (+https://t.me/versavija)',
            'Accept': 'image/*,*/*;q=0.8'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get('Content-Type', '').lower()
            if 'image' not in content_type:
                return (None, None)
            data = resp.read()
            digest = hashlib.sha256(data).hexdigest()
            ext = mimetypes.guess_extension(content_type.split(';')[0]) or '.jpg'
            fd, path = tempfile.mkstemp(prefix='bd_', suffix=ext)
            with open(fd, 'wb') as f:
                f.write(data)
            return (path, digest)
    except Exception as e:
        logging.info('Ошибка скачивания изображения %s: %s', url, e)
        return (None, None)


def _get_recent_image_hashes() -> list[str]:
    try:
        raw = get_setting(HISTORY_KEY_LAST_IMAGES, '') or ''
        lst = json.loads(raw) if raw.strip().startswith('[') else []
        if isinstance(lst, list):
            return [str(x) for x in lst]
    except Exception:
        pass
    return []


def _remember_image_hash(h: str) -> None:
    try:
        hist = _get_recent_image_hashes()
        hist.append(h)
        if len(hist) > IMAGE_HISTORY_WINDOW:
            hist = hist[-IMAGE_HISTORY_WINDOW:]
        set_setting(HISTORY_KEY_LAST_IMAGES, json.dumps(hist, ensure_ascii=False))
    except Exception:
        pass


def _collect_image_candidates() -> list[tuple[str, str]]:
    """Return list of (kind, value) where kind in {'url','file'}"""
    if not _get_setting_bool('birthday_image_enabled', False):
        return []
    provider = (get_setting('birthday_image_provider', 'loremflickr') or 'loremflickr').strip().lower()
    candidates: list[tuple[str, str]] = []
    # Wikimedia free provider (no key required)
    if provider == 'wikimedia_api':
        query = (get_setting('birthday_image_query', 'Flowers') or 'Flowers').strip()
        wm_urls = _fetch_wikimedia_image_candidates(query)
        for u in wm_urls:
            candidates.append(('url', u))
        if candidates:
            return candidates
    # API providers first if chosen
    if provider in ('unsplash_api','pixabay_api','pexels_api'):
        query = (get_setting('birthday_image_query', 'flowers') or 'flowers').strip()
        api_urls = _fetch_api_image_candidates(provider, query)
        for u in api_urls:
            candidates.append(('url', u))
        if candidates:
            return candidates
    if provider == 'local':
        folder = Path(__file__).parent / 'media' / 'birthday_flowers'
        if folder.exists():
            files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ('.jpg','.jpeg','.png','.webp')]
            random.shuffle(files)
            for p in files:
                candidates.append(('file', str(p)))
        return candidates
    if provider == 'static_list':
        try:
            raw = get_setting('birthday_image_static_urls', '') or ''
            items = []
            if raw.strip().startswith('['):
                items = json.loads(raw)
            else:
                items = [x.strip() for x in raw.split(',') if x.strip()]
            random.shuffle(items)
            for u in items:
                candidates.append(('url', u))
        except Exception as e:
            logging.warning('Некорректный список birthday_image_static_urls: %s', e)
        return candidates
    # URL providers chain
    for u in _build_random_image_urls():
        candidates.append(('url', u))
    return candidates


def _fetch_api_image_candidates(provider: str, query: str) -> list[str]:
    provider = (provider or '').strip().lower()
    q = quote_plus(query or 'flowers')
    urls: list[str] = []
    try:
        if provider == 'unsplash_api':
            key = (get_setting('unsplash_access_key', '') or '').strip()
            if not key:
                return []
            req = urllib.request.Request(
                url=f"https://api.unsplash.com/photos/random?query={q}&orientation=landscape&content_filter=high&count=1",
                headers={"Authorization": f"Client-ID {key}", "Accept": "application/json", 'User-Agent': 'versavija-bot/1.0'},
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            item = data[0] if isinstance(data, list) and data else data
            u = (item or {}).get('urls', {}).get('regular')
            if u:
                urls.append(u)
        elif provider == 'pixabay_api':
            key = (get_setting('pixabay_api_key', '') or '').strip()
            if not key:
                return []
            api_url = f"https://pixabay.com/api/?key={key}&q={q}&image_type=photo&orientation=horizontal&per_page=50&safesearch=true"
            with urllib.request.urlopen(api_url, timeout=12) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            hits = data.get('hits', [])
            random.shuffle(hits)
            for h in hits[:6]:
                u = h.get('largeImageURL') or h.get('webformatURL')
                if u:
                    urls.append(u)
        elif provider == 'pexels_api':
            key = (get_setting('pexels_api_key', '') or '').strip()
            if not key:
                return []
            req = urllib.request.Request(
                url=f"https://api.pexels.com/v1/search?query={q}&orientation=landscape&per_page=30",
                headers={"Authorization": key, "Accept": "application/json", 'User-Agent': 'versavija-bot/1.0'},
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            photos = data.get('photos', [])
            random.shuffle(photos)
            for p in photos[:6]:
                src = p.get('src', {})
                u = src.get('large') or src.get('large2x') or src.get('original')
                if u:
                    urls.append(u)
    except Exception as e:
        logging.info('API провайдер %s не дал картинок: %s', provider, e)
    return urls


def _fetch_wikimedia_image_candidates(query: str) -> list[str]:
    terms = [t.strip() for t in (query or '').split(',') if t.strip()]
    if not terms:
        terms = ['Bouquets of flowers', 'Wedding bouquets', 'Bridal bouquets', 'Flower arrangements', 'Roses bouquets', 'Peonies bouquets']
    default_terms = ['Bouquets of flowers', 'Wedding bouquets', 'Bridal bouquets', 'Flower arrangements', 'Roses bouquets', 'Peonies bouquets', 'Tulip bouquets']
    items: list[tuple[int, str]] = []
    seen: set[str] = set()
    base = 'https://commons.wikimedia.org/w/api.php'
    strict = _get_setting_bool('birthday_image_flowers_strict', True)
    for term in terms + default_terms:
        term_norm = term.replace(' ', '_')
        if not term_norm.lower().startswith('category:'):
            term_norm = f'Category:{term_norm}'
        params = {
            'action': 'query',
            'generator': 'categorymembers',
            'gcmtitle': term_norm,
            'gcmnamespace': 6,
            'gcmtype': 'file',
            'gcmlimit': 50,
            'prop': 'imageinfo|categories',
            'iiprop': 'url',
            'iiurlwidth': 1200,
            'clshow': '!hidden',
            'cllimit': 50,
            'format': 'json',
            'formatversion': 2,
        }
        try:
            req = urllib.request.Request(
                base + '?' + urlencode(params),
                headers={'User-Agent': 'versavija-bot/1.0 (+https://t.me/versavija)'
            })
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            pages = data.get('query', {}).get('pages', [])
            for page in pages:
                title = page.get('title', '')
                cats = [c.get('title', '') for c in page.get('categories', [])]
                if strict and (_has_human_indicator(title, cats) or _has_wilted_indicator(title, cats)):
                    continue
                infos = page.get('imageinfo', [])
                if not infos:
                    continue
                info = infos[0]
                u = info.get('thumburl') or info.get('url')
                if not u or u in seen:
                    continue
                seen.add(u)
                s = _score_flower_candidate(title, cats)
                items.append((s, u))
        except Exception as e:
            logging.info('Wikimedia API (%s) не дал результатов: %s', term_norm, e)
    # sort by score desc, then randomize within top chunk
    items.sort(key=lambda x: x[0], reverse=True)
    top = items[:20] if len(items) > 20 else items
    random.shuffle(top)
    return [u for _, u in top[:8]]


HISTORY_KEY_LAST_MSGS = 'birthday_last_message_indices'
HISTORY_WINDOW = 25
HISTORY_KEY_LAST_IMAGES = 'birthday_last_image_hashes'
IMAGE_HISTORY_WINDOW = 10


def _choose_birthday_message() -> str:
    msgs = BIRTHDAY_MESSAGES
    try:
        raw = get_setting(HISTORY_KEY_LAST_MSGS, '') or ''
        last = json.loads(raw) if raw.strip().startswith('[') else []
        if not isinstance(last, list):
            last = []
        last_set = {int(x) for x in last if isinstance(x, (int, float))}
    except Exception:
        last_set = set()
        last = []
    candidates = [i for i in range(len(msgs)) if i not in last_set]
    if not candidates:
        candidates = list(range(len(msgs)))
    idx = random.choice(candidates)
    # persist history
    try:
        hist = [int(x) for x in last if isinstance(x, (int, float))]
        hist.append(idx)
        if len(hist) > HISTORY_WINDOW:
            hist = hist[-HISTORY_WINDOW:]
        set_setting(HISTORY_KEY_LAST_MSGS, json.dumps(hist, ensure_ascii=False))
    except Exception:
        pass
    return msgs[idx]


async def _send_channel_congrats_for(date_msk: date):
    try:
        with sqlite3.connect('data.db') as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute('SELECT user_id, username, first_name, last_name, birthdate FROM subscribers')
            rows = cur.fetchall()
    except Exception as e:
        logging.warning('Не удалось прочитать подписчиков для поздравлений: %s', e)
        return

    mm = date_msk.month
    dd = date_msk.day
    for r in rows:
        mmdd = _parse_birth_mmdd(r['birthdate'])
        if not mmdd:
            continue
        if mmdd == (mm, dd):
            key = f"congrats_sent:{date_msk.isoformat()}:{r['user_id']}"
            if get_setting(key, ''):
                continue
            mention = _mention(r['username'], r['user_id'], r['first_name'], r['last_name'])
            text = _choose_birthday_message().replace('{mention}', mention)
            try:
                items = _collect_image_candidates()
                sent = False
                recent_hashes = set(_get_recent_image_hashes())
                for kind, val in items:
                    try:
                        if kind == 'file':
                            try:
                                with open(val, 'rb') as f:
                                    data = f.read()
                                digest = hashlib.sha256(data).hexdigest()
                            except Exception:
                                digest = None
                            if digest and digest in recent_hashes:
                                logging.info('Пропускаю повторяющееся изображение (file)')
                                continue
                            await bot.send_photo(BIRTHDAY_CHANNEL_ID, photo=FSInputFile(val), caption=text)
                            if digest:
                                _remember_image_hash(digest)
                            sent = True
                            break
                        else:
                            tmp, digest = _download_image_with_fingerprint(val)
                            if tmp:
                                if digest and digest in recent_hashes:
                                    try:
                                        Path(tmp).unlink(missing_ok=True)
                                    except Exception:
                                        pass
                                    logging.info('Пропускаю повторяющееся изображение (url)')
                                    continue
                                try:
                                    await bot.send_photo(BIRTHDAY_CHANNEL_ID, photo=FSInputFile(tmp), caption=text)
                                    if digest:
                                        _remember_image_hash(digest)
                                    sent = True
                                    break
                                finally:
                                    try:
                                        Path(tmp).unlink(missing_ok=True)
                                    except Exception:
                                        pass
                            else:
                                logging.info('Ссылка не является изображением: %s', val)
                    except Exception as e_img:
                        logging.info('Не удалось отправить фото (%s: %s): %s', kind, val, e_img)
                if not sent:
                    await bot.send_message(BIRTHDAY_CHANNEL_ID, text)
                set_setting(key, '1')
                logging.info('🎂 Поздравление отправлено: %s', mention)
            except Exception as e:
                logging.warning('Не удалось отправить поздравление %s: %s', mention, e)


async def _send_dm_promos_for(date_msk: date):
    try:
        with sqlite3.connect('data.db') as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute('SELECT user_id, username, first_name, last_name, birthdate FROM subscribers')
            subs = cur.fetchall()
            # Пользователи, которые стартовали бота
            try:
                cur.execute('SELECT user_id FROM users')
                started = {row['user_id'] for row in cur.fetchall()}
            except Exception:
                started = set()
    except Exception as e:
        logging.warning('Не удалось прочитать подписчиков для DM-промо: %s', e)
        return

    mm_today = date_msk.month
    dd_today = date_msk.day
    for r in subs:
        mmdd = _parse_birth_mmdd(r['birthdate'])
        if not mmdd:
            continue
        next_bd = _next_birthday_from(mmdd[0], mmdd[1], date_msk)
        days = (next_bd - date_msk).days
        if days == 14:
            year_key = f"promo_sent:{next_bd.year}:{r['user_id']}"
            if get_setting(year_key, ''):
                continue
            if r['user_id'] not in started:
                # бот не может инициировать ЛС без старта
                logging.info('⚠️ Пропускаю DM для %s: пользователь не стартовал бота', r['username'] or r['user_id'])
                continue
            mention = _mention(r['username'], r['user_id'], r['first_name'], r['last_name'])
            text = (
                f"{mention}, скоро ваш День Рождения! 🎂\n\n"
                "Дарим персональную акцию: Скидка 5% на фотосессию за 5 дней до ДР и 5 дней после ДР. ✨\n\n"
                "Если хотите — помогу подобрать идею и локацию. Напишите, когда удобно обсудить! 💬"
            )
            try:
                await bot.send_message(r['user_id'], text)
                set_setting(year_key, '1')
                logging.info('📩 DM-акция отправлена: %s', mention)
            except Exception as e:
                logging.warning('Не удалось отправить DM %s: %s', mention, e)


def _now_msk() -> datetime:
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo('Europe/Moscow'))
        except Exception:
            pass
    # fallback без tz/базы: добавим +3 часа к UTC
    return datetime.utcnow() + timedelta(hours=3)


def _seconds_until_next(hour: int, minute: int, second: int = 0) -> float:
    now = _now_msk()
    target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return (target - now).total_seconds()


async def _daily_job():
    while True:
        # ждём до 08:00 МСК
        delay = _seconds_until_next(8, 0, 0)
        await asyncio.sleep(delay)
        today = _now_msk().date()
        try:
            await _send_channel_congrats_for(today)
        except Exception as e:
            logging.warning('Ошибка при отправке поздравлений: %s', e)
        try:
            await _send_dm_promos_for(today)
        except Exception as e:
            logging.warning('Ошибка при отправке DM промо: %s', e)


async def setup_birthday_scheduler():
    logging.info('🎂 Планировщик дней рождения активирован (ежедневно в 08:00 МСК)')
    asyncio.create_task(_daily_job())
