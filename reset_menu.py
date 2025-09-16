# Reset menu to default (add Promotions button)

import sqlite3
from db import DB_PATH

def reset_menu_to_default():
    """Reset menu setting to force using DEFAULT_MENU with new Promotions button"""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    # Remove saved menu to force using DEFAULT_MENU
    cur.execute("DELETE FROM settings WHERE key = 'menu'")
    con.commit()
    con.close()
    print("✅ Menu reset to default. Restart bot to see changes.")

if __name__ == "__main__":
    reset_menu_to_default()