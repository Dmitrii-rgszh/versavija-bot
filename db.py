import sqlite3
from pathlib import Path
import json
import os

# Allow overriding DB location via environment variable (e.g. for Docker volume)
_default_db = Path(__file__).parent / 'data.db'
DB_PATH = Path(os.getenv('DB_PATH', _default_db))


def init_db() -> None:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)')
    # Add category column for bookings (migration-safe)
    cur.execute('''CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        chat_id INTEGER,
        start_ts TEXT,
        status TEXT,
        category TEXT,
        reminder_sent INTEGER DEFAULT 0
    )''')
    # Migration: if old table (no category column), try to add
    try:
        cur.execute("PRAGMA table_info(bookings)")
        cols = {r[1] for r in cur.fetchall()}
        if 'category' not in cols:
            cur.execute('ALTER TABLE bookings ADD COLUMN category TEXT')
    except Exception:
        pass
    cur.execute('CREATE INDEX IF NOT EXISTS idx_bookings_start ON bookings(start_ts)')
    con.commit()
    con.close()


def get_menu(default: list | None = None) -> list:
    """Return menu as a list of button dicts: [{'text':..., 'callback':...}, ...]"""
    raw = get_setting('menu', None)
    if not raw:
        # if nothing saved, return default (or empty)
        return default or []
    try:
        saved = json.loads(raw)
    except Exception:
        return default or []

    # If caller provided a default list, ensure default buttons exist in saved menu
    # without removing user-created entries. Matching is done by 'callback' field.
    if default:
        try:
            existing_callbacks = {m.get('callback') for m in saved if isinstance(m, dict)}
            added = False
            for d in default:
                if not isinstance(d, dict):
                    continue
                c = d.get('callback')
                if c and c not in existing_callbacks:
                    saved.append(d)
                    existing_callbacks.add(c)
                    added = True
            if added:
                # persist merged menu so caller sees same menu next time
                set_setting('menu', json.dumps(saved, ensure_ascii=False))
        except Exception:
            # if merging fails, just return parsed saved menu
            pass
    return saved


def save_menu(menu: list) -> None:
    set_setting('menu', json.dumps(menu, ensure_ascii=False))


def get_pending_actions() -> dict:
    """Return pending actions dict (username -> action dict)."""
    raw = get_setting('pending_actions', None)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def save_pending_actions(pending: dict) -> None:
    set_setting('pending_actions', json.dumps(pending, ensure_ascii=False))


def get_setting(key: str, default: str | None = None) -> str | None:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('SELECT value FROM settings WHERE key=?', (key,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else default


def set_setting(key: str, value: str) -> None:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))
    con.commit()
    con.close()


# ----- Booking helpers -----
def add_booking(user_id: int, username: str, chat_id: int, start_ts: str, category: str) -> int:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('INSERT INTO bookings(user_id, username, chat_id, start_ts, status, category, reminder_sent) VALUES(?,?,?,?,?,?,0)',
                (user_id, username, chat_id, start_ts, 'active', category))
    bid = cur.lastrowid
    con.commit()
    con.close()
    return bid


def get_bookings_between(start_iso: str, end_iso: str) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('SELECT id,user_id,username,chat_id,start_ts,status,category,reminder_sent FROM bookings WHERE start_ts>=? AND start_ts<? AND status IN ("active","confirmed") ORDER BY start_ts', (start_iso, end_iso))
    rows = cur.fetchall()
    con.close()
    return [
        {'id': r[0], 'user_id': r[1], 'username': r[2], 'chat_id': r[3], 'start_ts': r[4], 'status': r[5], 'category': r[6], 'reminder_sent': r[7]} for r in rows
    ]


def is_slot_taken(start_ts: str) -> bool:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('SELECT 1 FROM bookings WHERE start_ts=? AND status IN ("active","confirmed") LIMIT 1', (start_ts,))
    taken = cur.fetchone() is not None
    con.close()
    return taken


def get_booking(bid: int) -> dict | None:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('SELECT id,user_id,username,chat_id,start_ts,status,category,reminder_sent FROM bookings WHERE id=?', (bid,))
    r = cur.fetchone()
    con.close()
    if not r:
        return None
    return {'id': r[0], 'user_id': r[1], 'username': r[2], 'chat_id': r[3], 'start_ts': r[4], 'status': r[5], 'category': r[6], 'reminder_sent': r[7]}


def get_active_booking_for_user(user_id: int) -> dict | None:
    """Return the latest active booking (status active/confirmed) for a user, if any."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('''SELECT id,user_id,username,chat_id,start_ts,status,category,reminder_sent FROM bookings
                   WHERE user_id=? AND status IN ("active","confirmed") ORDER BY start_ts DESC LIMIT 1''', (user_id,))
    r = cur.fetchone()
    con.close()
    if not r:
        return None
    return {'id': r[0], 'user_id': r[1], 'username': r[2], 'chat_id': r[3], 'start_ts': r[4], 'status': r[5], 'category': r[6], 'reminder_sent': r[7]}


def update_booking_time_and_category(bid: int, new_start_ts: str, new_category: str):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('UPDATE bookings SET start_ts=?, category=?, reminder_sent=0 WHERE id=?', (new_start_ts, new_category, bid))
    con.commit()
    con.close()


def update_booking_status(bid: int, status: str):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('UPDATE bookings SET status=? WHERE id=?', (status, bid))
    con.commit()
    con.close()


def mark_booking_reminder_sent(bid: int):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('UPDATE bookings SET reminder_sent=1 WHERE id=?', (bid,))
    con.commit()
    con.close()


def get_due_reminders(from_iso: str, to_iso: str) -> list[dict]:
    """Return bookings whose reminder should be sent in [from_iso, to_iso)."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('''SELECT id,user_id,username,chat_id,start_ts,status,category,reminder_sent FROM bookings
                   WHERE status IN ("active","confirmed") AND reminder_sent=0 AND start_ts>=? AND start_ts<?''', (from_iso, to_iso))
    rows = cur.fetchall()
    con.close()
    return [
        {'id': r[0], 'user_id': r[1], 'username': r[2], 'chat_id': r[3], 'start_ts': r[4], 'status': r[5], 'category': r[6], 'reminder_sent': r[7]} for r in rows
    ]


def clear_all_bookings():
    """Dangerous: wipe all booking data."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('DELETE FROM bookings')
    con.commit()
    con.close()
