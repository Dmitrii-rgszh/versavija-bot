"""Utility helpers: transliterate Cyrillic to Latin and normalize callback strings."""
import re
from urllib.parse import urlparse, parse_qs, quote_plus, unquote
import asyncio
try:
    import aiohttp
except Exception:
    aiohttp = None
from typing import Optional, Tuple

# --- Coordinates helpers ---
def _valid_lat_lon(lat: float, lon: float) -> bool:
    return (-90 <= lat <= 90) and (-180 <= lon <= 180)


def _parse_lon_lat_value(val: str) -> Optional[Tuple[float, float]]:
    """Parse string containing coordinates like 'lon,lat' or 'lat,lon'. Return (lat, lon) or None."""
    try:
        if not val:
            return None
        s = unquote(val)
        parts = [p.strip() for p in s.split(',')]
        if len(parts) < 2:
            return None
        a = float(parts[0])
        b = float(parts[1])
        # Prefer Yandex order lon,lat
        if _valid_lat_lon(b, a):
            return b, a
        if _valid_lat_lon(a, b):
            return a, b
    except Exception:
        return None
    return None

# Simple transliteration map for Russian Cyrillic -> Latin (lowercase)
_TRANSLIT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'i',
    'к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f',
    'х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'
}

def transliterate(text: str) -> str:
    if not text:
        return ''
    out = []
    for ch in text:
        lower = ch.lower()
        if lower in _TRANSLIT:
            out.append(_TRANSLIT[lower])
        else:
            out.append(ch)
    return ''.join(out)


def normalize_callback(text: str) -> str:
    """Normalize arbitrary text into a callback-safe string.

    Steps:
    - transliterate Cyrillic to Latin
    - replace spaces and runs of non-alnum/_/- with underscore
    - lowercase
    - collapse multiple underscores, trim leading/trailing underscores
    - if empty, return 'btn'
    """
    if not text:
        return 'btn'
    t = transliterate(text)
    # keep ASCII letters, digits, underscore and hyphen; replace others with underscore
    t = re.sub(r'[^A-Za-z0-9_\-]+', '_', t)
    t = re.sub(r'_+', '_', t)
    t = t.strip('_')
    t = t.lower()
    if not t:
        return 'btn'
    return t


def yandex_link_for_city(center_lat: float, center_lon: float, city: str, zoom: int = 16) -> str:
    ll = f"{center_lon:.6f},{center_lat:.6f}"
    city_enc = quote_plus(city)
    return f"https://yandex.ru/maps/?z={zoom}&ll={ll}&text={city_enc}"


def parse_yandex_coords(url: str) -> tuple[float, float] | None:
    try:
        u = url.strip()
        if not (u.startswith("http://") or u.startswith("https://")):
            u = "https://" + u
        parsed = urlparse(u)
        if not parsed.netloc or 'yandex' not in parsed.netloc:
            return None
        qs = parse_qs(parsed.query)
        # Common keys first
        for key in ('ll', 'pt', 'rll', 'whatshere[point]'):
            if key in qs and qs[key]:
                coords = _parse_lon_lat_value(qs[key][0])
                if coords:
                    return coords
        # Scan any query value for lon,lat
        for values in qs.values():
            for v in values:
                coords = _parse_lon_lat_value(v)
                if coords:
                    return coords
        frag = parsed.fragment
        if frag:
            fqs = parse_qs(frag)
            for key in ('ll', 'pt', 'rll', 'whatshere[point]'):
                if key in fqs and fqs[key]:
                    coords = _parse_lon_lat_value(fqs[key][0])
                    if coords:
                        return coords
            for values in fqs.values():
                for v in values:
                    coords = _parse_lon_lat_value(v)
                    if coords:
                        return coords
    except Exception:
        return None
    return None


async def resolve_yandex_url(url: str, max_redirects: int = 5) -> str:
    """Follow redirects to resolve Yandex short links like /maps/-/XXXX.

    Returns the final URL (or original if resolution fails or aiohttp unavailable).
    """
    if aiohttp is None:
        return url
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            current = url
            for _ in range(max_redirects):
                try:
                    async with session.head(current, allow_redirects=False) as resp:
                        if 300 <= resp.status < 400 and 'Location' in resp.headers:
                            loc = resp.headers.get('Location')
                            # Build absolute URL if needed
                            if loc.startswith('/'):
                                parsed = urlparse(current)
                                current = f"{parsed.scheme}://{parsed.netloc}{loc}"
                            else:
                                current = loc
                            continue
                        # If not redirect, try to use resp.url (normalized)
                        return str(resp.url)
                except Exception:
                    # Fallback to GET with redirects
                    async with session.get(current, allow_redirects=True) as resp2:
                        return str(resp2.url)
            return current
    except Exception:
        return url


def parse_plain_coords(text: str) -> Optional[Tuple[float, float]]:
    """Parse plain 'lat, lon' text from user message."""
    try:
        m = re.search(r'([\-]?\d{1,3}\.\d+)\s*,\s*([\-]?\d{1,3}\.\d+)', text)
        if not m:
            return None
        a = float(m.group(1))
        b = float(m.group(2))
        # assume lat, lon order for plain text
        if -90 <= a <= 90 and -180 <= b <= 180:
            return a, b
        # try swapped
        if -90 <= b <= 90 and -180 <= a <= 180:
            return b, a
    except Exception:
        return None
    return None


async def fetch_yandex_coords_from_html(url: str) -> Optional[Tuple[float, float]]:
    """Fetch Yandex page and try to extract coordinates from HTML content.

    Strategies:
    - Try canonical/og:url/meta-refresh to get a full URL with coords
    - Search raw or encoded ll/pt in HTML
    - Search 'Координаты: <lat>, <lon>'
    - Search JSON-like '"coordinates": [<lon>, <lat>]', 'center'/ 'll' arrays
    - Search '"latitude": <lat>, "longitude": <lon>'
    """
    if aiohttp is None:
        return None
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, allow_redirects=True) as resp:
                html = await resp.text(errors='ignore')
                # Meta/canonical/og:url
                m = re.search(r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if m:
                    c_url = m.group(1)
                    coords = parse_yandex_coords(c_url)
                    if coords:
                        return coords
                m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if m:
                    c_url = m.group(1)
                    coords = parse_yandex_coords(c_url)
                    if coords:
                        return coords
                m = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\']\d+;\s*url=([^"\']+)["\']', html, re.IGNORECASE)
                if m:
                    c_url = unquote(m.group(1))
                    coords = parse_yandex_coords(c_url)
                    if coords:
                        return coords
                # 1) Координаты: lat, lon
                m = re.search(r'Координаты[^0-9\-]*([\-]?\d{1,3}\.\d+)\s*,\s*([\-]?\d{1,3}\.\d+)', html)
                if m:
                    lat = float(m.group(1)); lon = float(m.group(2))
                    if _valid_lat_lon(lat, lon):
                        return lat, lon
                # 0b) Явный JS-редирект на полный URL
                m = re.search(r'location\.(?:href|replace)\s*=\s*["\']([^"\']+)["\']', html)
                if m:
                    c_url = m.group(1)
                    coords = parse_yandex_coords(c_url)
                    if coords:
                        return coords
                m = re.search(r'window\.(?:location|top\.location)\s*=\s*["\']([^"\']+)["\']', html)
                if m:
                    c_url = m.group(1)
                    coords = parse_yandex_coords(c_url)
                    if coords:
                        return coords
                # 1a) ll= / pt= present in the HTML (raw or percent-encoded)
                m = re.search(r'[?&#]ll=([\-]?\d{1,3}\.\d+),([\-]?\d{1,3}\.\d+)', html)
                if m:
                    lon = float(m.group(1)); lat = float(m.group(2))
                    if _valid_lat_lon(lat, lon):
                        return lat, lon
                m = re.search(r'(?:ll%3D|%3All%3D)([\-]?\d{1,3}\.\d+)%2C([\-]?\d{1,3}\.\d+)', html, re.IGNORECASE)
                if m:
                    lon = float(m.group(1)); lat = float(m.group(2))
                    if _valid_lat_lon(lat, lon):
                        return lat, lon
                m = re.search(r'(?:pt%3D|whatshere%5Bpoint%5D=)([\-]?\d{1,3}\.\d+)%2C([\-]?\d{1,3}\.\d+)', html, re.IGNORECASE)
                if m:
                    lon = float(m.group(1)); lat = float(m.group(2))
                    if _valid_lat_lon(lat, lon):
                        return lat, lon
                # 2) "coordinates": [lon, lat]
                m = re.search(r'"coordinates"\s*:\s*\[\s*([\-]?\d{1,3}\.\d+)\s*,\s*([\-]?\d{1,3}\.\d+)\s*\]', html)
                if m:
                    lon = float(m.group(1)); lat = float(m.group(2))
                    if _valid_lat_lon(lat, lon):
                        return lat, lon
                # 2a) center/ll arrays
                m = re.search(r'"(?:center|ll)"\s*:\s*\[\s*([\-]?\d{1,3}\.\d+)\s*,\s*([\-]?\d{1,3}\.\d+)\s*\]', html)
                if m:
                    lon = float(m.group(1)); lat = float(m.group(2))
                    if _valid_lat_lon(lat, lon):
                        return lat, lon
                # 3) "latitude": lat, "longitude": lon
                m = re.search(r'"lat(?:itude)?"\s*:\s*([\-]?\d{1,3}\.\d+)\s*,\s*"lon(?:gitude)?"\s*:\s*([\-]?\d{1,3}\.\d+)', html)
                if m:
                    lat = float(m.group(1)); lon = float(m.group(2))
                    if _valid_lat_lon(lat, lon):
                        return lat, lon
                # 3a) nested object like {"geoPoint":{"lon":...,"lat":...}}
                m = re.search(r'"geoPoint"\s*:\s*\{[^}]*"lon"\s*:\s*([\-]?\d{1,3}\.\d+)\s*,\s*"lat"\s*:\s*([\-]?\d{1,3}\.\d+)', html)
                if m:
                    lon = float(m.group(1)); lat = float(m.group(2))
                    if _valid_lat_lon(lat, lon):
                        return lat, lon
                # 3b) Скан всех URL внутри HTML на предмет ll/pt
                for m in re.finditer(r'https?://[^\s"\'>)]+', html):
                    u = m.group(0)
                    if 'yandex.' not in u and 'ya.ru' not in u:
                        continue
                    coords = parse_yandex_coords(u)
                    if coords:
                        return coords
                # 4) Fallback: try to extract an address string and geocode via Nominatim
                addr = None
                m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if m:
                    addr = m.group(1)
                if not addr:
                    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                    if m:
                        addr = m.group(1)
                if not addr:
                    m = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
                    if m:
                        addr = m.group(1)
                if addr:
                    # Clean typical prefixes like 'Yandex Maps — '
                    addr = re.sub(r'^\s*Yandex\s+Maps\s*[—\-:]\s*', '', addr, flags=re.IGNORECASE)
                    # Drop trailing generic text after address if present
                    addr = addr.strip()
                    try:
                        coords = await _geocode_nominatim(addr)
                        if coords:
                            return coords
                    except Exception:
                        pass
    except Exception:
        return None
    return None


async def _geocode_nominatim(query: str) -> Optional[Tuple[float, float]]:
    """Geocode a free-form address using OpenStreetMap Nominatim (no API key).
    Respects polite usage with User-Agent and RU language.
    """
    if aiohttp is None:
        return None
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': query,
        'format': 'json',
        'limit': '1',
        'accept-language': 'ru'
    }
    headers = {
        'User-Agent': 'versavija-bot/1.0 (contact: none)'
    }
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
                if isinstance(data, list) and data:
                    item = data[0]
                    lat = float(item.get('lat'))
                    lon = float(item.get('lon'))
                    if _valid_lat_lon(lat, lon):
                        return lat, lon
    except Exception:
        return None
    return None


async def reverse_geocode_nominatim(lat: float, lon: float) -> Optional[str]:
    """Reverse geocode coordinates to a human-readable RU address using Nominatim."""
    if aiohttp is None:
        return None

    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        'lat': f"{lat:.6f}",
        'lon': f"{lon:.6f}",
        'format': 'jsonv2',
        'addressdetails': '1',
        'accept-language': 'ru'
    }
    headers = {
        'User-Agent': 'versavija-bot/1.0 (contact: none)'
    }

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    addr = data.get('address') or {}
    locality = addr.get('city') or addr.get('town') or addr.get('municipality') or addr.get('village') or addr.get('hamlet')
    road = addr.get('road') or addr.get('pedestrian') or addr.get('footway') or addr.get('residential')
    house = addr.get('house_number') or addr.get('house')
    suburb = addr.get('suburb') or addr.get('neighbourhood')

    parts: list[str] = []
    if locality:
        parts.append(f"г. {locality}")
    if suburb:
        parts.append(suburb)
    if road:
        parts.append(f"ул. {road}")
    if house:
        parts.append(f"д. {house}")

    if parts:
        return ", ".join(parts)

    display_name = data.get('display_name')
    if isinstance(display_name, str) and display_name.strip():
        return ", ".join(display_name.split(',')[:5]).strip()
    return None


def parse_yandex_address_from_url(url: str) -> Optional[str]:
    """Extract a human-readable address from Yandex Maps URL if present.

    Heuristics:
    - Use 'text' query parameter if it looks like an address (contains digits or street keywords).
    """
    try:
        if not (url.startswith('http://') or url.startswith('https://')):
            url = 'https://' + url
        p = urlparse(url)
        if 'yandex' not in p.netloc:
            return None
        qs = parse_qs(p.query)
        txt = None
        if 'text' in qs and qs['text']:
            txt = unquote(qs['text'][0])
        if txt and any(k in txt.lower() for k in ('ул', 'улица', 'пр', 'просп', 'дом', 'д.', 'корп', 'к.', 'бул', 'пл', 'шос', 'стр', 'house', 'street')):
            return txt.strip()
    except Exception:
        return None
    return None


async def fetch_yandex_address_from_html(url: str) -> Optional[str]:
    """Fetch Yandex page and try to extract a human-readable address directly from HTML.

    Strategies:
    - meta og:title / meta description / <title>
    - JSON-like fragments with "address" or "fullAddress"
    """
    if aiohttp is None:
        return None
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, allow_redirects=True) as resp:
                html = await resp.text(errors='ignore')
                # Prefer explicit address-like JSON fields
                m = re.search(r'"fullAddress"\s*:\s*"([^"]+)"', html)
                if m:
                    return unquote(m.group(1)).strip()
                m = re.search(r'"address"\s*:\s*\{[^}]*"formatted"\s*:\s*\[([^\]]+)\]', html)
                if m:
                    parts_raw = m.group(1)
                    parts = [re.sub(r'^\s*"|"\s*$', '', s).strip() for s in parts_raw.split(',')]
                    parts = [p for p in parts if p]
                    if parts:
                        return ', '.join(parts[:6])
                # Fallback to meta tags
                m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if m:
                    title = m.group(1)
                    title = re.sub(r'^\s*Yandex\s+Maps\s*[—\-:]\s*', '', title, flags=re.IGNORECASE)
                    if title and any(ch.isdigit() for ch in title):
                        return title.strip()
                m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if m:
                    desc = m.group(1).strip()
                    if any(ch.isdigit() for ch in desc) and len(desc) <= 140:
                        return desc
                m = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
                if m:
                    t = m.group(1)
                    t = re.sub(r'^\s*Yandex\s+Maps\s*[—\-:]\s*', '', t, flags=re.IGNORECASE)
                    if t and any(ch.isdigit() for ch in t):
                        return t.strip()
    except Exception:
        return None
    return None
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            'lat': f"{lat:.6f}",
            'lon': f"{lon:.6f}",
            'format': 'jsonv2',
            'addressdetails': '1',
            'accept-language': 'ru'
        }
        headers = {
            'User-Agent': 'versavija-bot/1.0 (contact: none)'
        }
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
                addr = (data or {}).get('address') or {}
                # pick best locality label
                locality = addr.get('city') or addr.get('town') or addr.get('municipality') or addr.get('village') or addr.get('hamlet')
                road = addr.get('road') or addr.get('pedestrian') or addr.get('footway') or addr.get('residential')
                house = addr.get('house_number') or addr.get('house')
                # Optional sublocality (e.g., микрорайон)
                suburb = addr.get('suburb') or addr.get('neighbourhood')

                parts: list[str] = []
                if locality:
                    # Prefix city/town with "г." for common RU style
                    parts.append(f"г. {locality}")
                if suburb:
                    # Include sublocality if available
                    parts.append(suburb)
                if road:
                    parts.append(f"ул. {road}")
                if house:
                    parts.append(f"д. {house}")

                if parts:
                    return ", ".join(parts)

                # Fallback: provider's display_name
                disp = (data or {}).get('display_name')
                if isinstance(disp, str) and disp.strip():
                    # Trim country if overly long
                    return ", ".join(disp.split(',')[:5]).strip()
                return None
    except Exception:
        return None
