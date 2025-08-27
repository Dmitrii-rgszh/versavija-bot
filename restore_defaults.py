"""
Миграция: восстановить дефолтные кнопки в начале меню, не потеряв пользовательские кнопки.
Запускается локально: сохранит новый список в `data.db` и выведет итоговый JSON.
"""
import json
from db import get_menu, save_menu

DEFAULTS = [
    {"text": "Портфолио", "callback": "portfolio"},
    {"text": "Услуги и цены", "callback": "services"},
    {"text": "Онлайн-запись", "callback": "booking"},
    {"text": "Отзывы", "callback": "reviews"},
    {"text": "Соцсети", "callback": "social"},
]

if __name__ == '__main__':
    # Получаем текущий сохранённый список (без автоматического добавления дефолтов)
    saved = get_menu(None)
    # Список callback дефолтов в порядке
    default_callbacks = [d.get('callback') for d in DEFAULTS if isinstance(d, dict)]

    # Построим новый список: для каждого дефолта добавим сохранённый элемент с тем же callback, если есть,
    # иначе добавим дефолтный элемент. Затем добавим все оставшиеся сохранённые элементы (пользовательские).
    saved_map = {}
    for item in saved:
        if not isinstance(item, dict):
            continue
        cb = item.get('callback')
        # Сохраняем только первые встретившиеся по callback (чтобы держать порядок из сохранения)
        if cb and cb not in saved_map:
            saved_map[cb] = item

    new_menu = []
    for d in DEFAULTS:
        cb = d.get('callback')
        if cb and cb in saved_map:
            new_menu.append(saved_map.pop(cb))
        else:
            new_menu.append(d)

    # append remaining saved items in their original order (skip callbacks already used)
    for item in saved:
        if not isinstance(item, dict):
            continue
        cb = item.get('callback')
        if not cb or cb in default_callbacks:
            # already included above
            continue
        # still present in saved_map (not merged yet)
        if cb in saved_map:
            new_menu.append(saved_map.pop(cb))

    save_menu(new_menu)
    print('Saved merged menu:')
    print(json.dumps(new_menu, ensure_ascii=False, indent=2))
