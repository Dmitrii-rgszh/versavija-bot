from __future__ import annotations

from typing import Dict, Any

from db import get_pending_actions, save_pending_actions

__all__ = ["ADMIN_PENDING_ACTIONS"]


def _load_pending_actions() -> Dict[str, Any]:
    try:
        actions = get_pending_actions() or {}
    except Exception:
        return {}

    if actions:
        legacy = [
            key
            for key, value in list(actions.items())
            if (
                (isinstance(value, dict) and value.get('action') in {'broadcast_text', 'broadcast_image'})
                or (isinstance(value, str) and value.startswith('broadcast'))
            )
        ]
        if legacy:
            for key in legacy:
                actions.pop(key, None)
            try:
                save_pending_actions(actions)
            except Exception:
                pass
    return actions


ADMIN_PENDING_ACTIONS: Dict[str, Any] = _load_pending_actions()
