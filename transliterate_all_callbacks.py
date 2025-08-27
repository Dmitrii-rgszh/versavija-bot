"""
Миграция: автоматически транслитерировать все кириллические callback'ы в латиницу,
нормализовать их и безопасно разрешить коллизии добавлением суффиксов.
- Делает резервную копию текущего меню в settings под ключом 'menu_backup'.
- Преобразует callback каждого элемента с помощью normalize_callback.
- Если получается дубликат, добавляет порядковый суффикс: _1, _2, ...
- Сохраняет новое меню и печатает карту изменений.
"""
import json
import time
from db import get_menu, save_menu, get_setting, set_setting
from utils import normalize_callback

BACKUP_KEY = 'menu_backup'


def main():
    # read current saved menu without merging defaults
    saved = get_menu(None)
    if not isinstance(saved, list):
        print('No menu found or invalid format; aborting')
        return

    # store backup (timestamped)
    ts = int(time.time())
    backup_value = json.dumps(saved, ensure_ascii=False)
    # also keep a latest backup key
    set_setting(f'{BACKUP_KEY}_{ts}', backup_value)
    set_setting(BACKUP_KEY, backup_value)
    print(f'Backup saved to settings keys: {BACKUP_KEY} and {BACKUP_KEY}_{ts}')

    # build current set of callbacks
    existing = [m.get('callback') for m in saved if isinstance(m, dict) and m.get('callback')]
    # we'll replace callbacks with normalized versions, resolving collisions
    used = set()
    mapping = {}
    new_menu = []

    for item in saved:
        if not isinstance(item, dict):
            new_menu.append(item)
            continue
        orig_cb = item.get('callback') or ''
        # normalize the original callback (transliterate + cleanup)
        new_cb = normalize_callback(orig_cb)
        # ensure uniqueness
        base = new_cb or 'btn'
        candidate = base
        i = 1
        while candidate in used:
            candidate = f"{base}_{i}"
            i += 1
        used.add(candidate)
        mapping[orig_cb] = candidate
        new_item = dict(item)
        new_item['callback'] = candidate
        new_menu.append(new_item)

    save_menu(new_menu)
    print('Migration complete. Mapping (original -> new):')
    print(json.dumps(mapping, ensure_ascii=False, indent=2))
    print('Resulting menu:')
    print(json.dumps(new_menu, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
