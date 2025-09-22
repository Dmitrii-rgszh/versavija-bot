from __future__ import annotations

from typing import Dict, List, Tuple

# track last shown photo index per chat+category to avoid repeats
LAST_CATEGORY_PHOTO: Dict[Tuple[int, str], int] = {}

# In-memory state containers (not persisted unless explicitly written via set_setting)
UNDO_DELETED_CATEGORY: Dict[str, Dict] = {}
UNDO_DELETED_CATEGORY_PHOTOS: Dict[str, List] = {}
UNDO_DELETED_PHOTO: Dict[str, str] = {}

def reset_last_category_position(slug: str) -> None:
    """Сбросить последнюю позицию просмотра для всех чатов по категории."""
    keys_to_remove = [key for key in LAST_CATEGORY_PHOTO if key[1] == slug]
    for key in keys_to_remove:
        LAST_CATEGORY_PHOTO.pop(key, None)


__all__ = [
    "LAST_CATEGORY_PHOTO",
    "UNDO_DELETED_CATEGORY",
    "UNDO_DELETED_CATEGORY_PHOTOS",
    "UNDO_DELETED_PHOTO",
    "reset_last_category_position",
]
