"""Асинхронные обёртки над синхронными функциями модуля db."""
from __future__ import annotations

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Iterable

import db as _sync_db

__all__ = [
    "init_db",
    "get_setting",
    "set_setting",
    "get_menu",
    "save_menu",
    "get_pending_actions",
    "save_pending_actions",
    "add_booking",
    "is_slot_taken",
    "get_bookings_between",
    "get_booking",
    "update_booking_status",
    "clear_all_bookings",
    "get_active_booking_for_user",
    "update_booking_time_and_category",
    "update_booking_time_category_location",
    "add_user",
    "get_all_users",
    "add_promotion",
    "get_active_promotions",
    "get_all_promotions",
    "delete_promotion",
    "cleanup_expired_promotions",
    "toggle_photo_like",
    "get_photo_likes_count",
    "user_has_liked_photo",
    "mark_booking_reminder_sent",
    "get_due_reminders",
]


_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="db-worker")


def _asyncify(fn: Callable[..., Any]) -> Callable[..., Any]:
    async def wrapper(*args: Iterable[Any], **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        bound = functools.partial(fn, *args, **kwargs)
        return await loop.run_in_executor(_executor, bound)

    return wrapper


# Автоматически создаём асинхронные версии для перечисленных функций
for _name in __all__:
    globals()[_name] = _asyncify(getattr(_sync_db, _name))  # type: ignore[misc]


def shutdown_executor() -> None:
    """Завершить executor при выключении приложения."""
    _executor.shutdown(wait=False, cancel_futures=True)

