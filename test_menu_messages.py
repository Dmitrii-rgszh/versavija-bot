#!/usr/bin/env python3
"""
Test script to verify menu messages constants
"""

import sys
sys.path.append('.')

from handlers import MENU_MESSAGES

print("🔍 Проверка констант MENU_MESSAGES:")
for key, value in MENU_MESSAGES.items():
    print(f"  {key}: '{value}'")

print(f"\n✅ Главное меню должно показывать: '{MENU_MESSAGES['main']}'")

# Let's also verify the constant is correct
expected = "👇 Выберите действие:"
actual = MENU_MESSAGES["main"]

if actual == expected:
    print("✅ Константа правильная - содержит эмодзи 👇")
else:
    print(f"❌ Проблема с константой!")
    print(f"   Ожидалось: '{expected}'")
    print(f"   Фактически: '{actual}'")