from __future__ import annotations

from typing import Set

import db_async
from config import ADMIN_IDS
from keyboards import ADMIN_USERNAMES


def user_is_admin(username: str, user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    return username in ADMIN_USERNAMES


async def add_known_admin(user_id: int) -> None:
    try:
        raw = await db_async.get_setting('admin_known_ids', '') or ''
        ids = {int(x) for x in raw.split(',') if x.strip().isdigit()}
        if user_id not in ids:
            ids.add(user_id)
            await db_async.set_setting('admin_known_ids', ','.join(str(i) for i in sorted(ids)))
    except Exception:
        pass


async def get_all_admin_ids() -> Set[int]:
    ids: Set[int] = set(ADMIN_IDS)
    try:
        raw = await db_async.get_setting('admin_known_ids', '') or ''
        for part in raw.split(','):
            part = part.strip()
            if part.isdigit():
                ids.add(int(part))
    except Exception:
        pass
    return ids


async def is_admin_view_enabled(username: str, user_id: int) -> bool:
    if not user_is_admin(username, user_id):
        return False
    val = await db_async.get_setting(f'admin_mode_{user_id}', 'on') or 'on'
    return val == 'on'
