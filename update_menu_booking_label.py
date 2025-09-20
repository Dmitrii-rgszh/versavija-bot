import sqlite3
from db import DB_PATH, get_menu, save_menu
from handlers import DEFAULT_MENU

TARGET_CALLBACK = 'booking'
NEW_TEXT = '📅 Запись'

def main():
    # Load current menu (merged with defaults to ensure structure)
    menu = get_menu(DEFAULT_MENU)
    changed = False
    for item in menu:
        try:
            if item.get('callback') == TARGET_CALLBACK and item.get('text') != NEW_TEXT:
                item['text'] = NEW_TEXT
                changed = True
        except Exception:
            pass
    if changed:
        save_menu(menu)
        print('✅ Updated menu label to', NEW_TEXT)
    else:
        print('ℹ️ No change needed; label already set to', NEW_TEXT)

if __name__ == '__main__':
    main()
