#!/usr/bin/env python3
"""
Script to update portfolio categories with emoji icons
"""

from db import set_setting
import json

# Updated portfolio categories with emoji
UPDATED_PORTFOLIO_CATEGORIES = [
    {"text": "👨‍👩‍👧‍👦 Семейная", "slug": "family"},
    {"text": "💕 Love Story", "slug": "love_story"},
    {"text": "👤 Индивидуальная", "slug": "personal"},
    {"text": "🎉 Репортажная (банкеты, мероприятия)", "slug": "reportage"},
    {"text": "💍 Свадебная", "slug": "wedding"},
    {"text": "💋 Lingerie (будуарная)", "slug": "lingerie"},
    {"text": "👶 Детская (школы/садики)", "slug": "children"},
    {"text": "👩‍👶 Мама с ребёнком", "slug": "mom_child"},
    {"text": "✝️ Крещение", "slug": "baptism"},
    {"text": "⛪ Венчание", "slug": "wedding_church"},
]

if __name__ == "__main__":
    # Update portfolio categories in database
    set_setting('portfolio_categories', json.dumps(UPDATED_PORTFOLIO_CATEGORIES, ensure_ascii=False))
    print("✅ Portfolio categories updated with emoji icons!")
    print("Categories:")
    for cat in UPDATED_PORTFOLIO_CATEGORIES:
        print(f"  - {cat['text']} ({cat['slug']})")