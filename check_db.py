import sqlite3
import json

conn = sqlite3.connect('data.db')
cursor = conn.cursor()

print("=== Восстанавливаем категории портфолио ===")
categories = [
    {"text": "Семейная", "slug": "family"},
    {"text": "Love Story", "slug": "love_story"},
    {"text": "Индивидуальная", "slug": "personal"},
    {"text": "Репортажная (банкеты, мероприятия)", "slug": "reportage"},
    {"text": "Свадебная", "slug": "wedding"},
    {"text": "Lingerie (будуарная)", "slug": "lingerie"},
    {"text": "Детская (школы/садики)", "slug": "children"},
    {"text": "Мама с ребёнком", "slug": "mom_child"},
    {"text": "Крещение", "slug": "baptism"},
    {"text": "Венчание", "slug": "wedding_church"}
]

categories_json = json.dumps(categories, ensure_ascii=False)
cursor.execute("UPDATE settings SET value = ? WHERE key = 'portfolio_categories'", (categories_json,))
conn.commit()

print("=== Проверяем результат ===")
cursor.execute("SELECT key, value FROM settings WHERE key = 'portfolio_categories'")
result = cursor.fetchone()
print(f"Категории восстановлены: {len(categories)} категорий")

conn.close()
print("Категории восстановлены!")
