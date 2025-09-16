#!/usr/bin/env python3
"""
Тест для проверки правильного размещения кнопок портфолио на мобильном устройстве.
Длинные кнопки должны размещаться по одной в строке.
"""

import sys
import os

# Add the current directory to Python path to import modules
sys.path.insert(0, os.getcwd())

from keyboards import build_portfolio_keyboard

def test_portfolio_keyboard_layout():
    """Проверяет размещение кнопок в клавиатуре портфолио"""
    
    # Тестовые категории (как в реальном коде)
    test_categories = [
        {"text": "👨‍👩‍👧‍👦 Семейная", "slug": "family"},
        {"text": "💕 Love Story", "slug": "love_story"},
        {"text": "👤 Индивидуальная", "slug": "personal"},
        {"text": "🎉 Репортажная (банкеты, мероприятия)", "slug": "reportage"},  # Длинная
        {"text": "💍 Свадебная", "slug": "wedding"},
        {"text": "💋 Lingerie (будуарная)", "slug": "lingerie"},  # Длинная
        {"text": "👶 Детская (школы/садики)", "slug": "children"},
        {"text": "👩‍👶 Мама с ребёнком", "slug": "mom_child"},
    ]
    
    kb = build_portfolio_keyboard(test_categories, is_admin=False)
    
    print("🔍 Анализ размещения кнопок портфолио:")
    print("-" * 50)
    
    issues = []
    single_button_rows = []
    
    for i, row in enumerate(kb.inline_keyboard):
        row_texts = [btn.text for btn in row]
        
        print(f"Строка {i+1}: {len(row)} кнопок - {row_texts}")
        
        # Проверяем длинные кнопки
        for btn_text in row_texts:
            if "Репортажная (банкеты, мероприятия)" in btn_text:
                if len(row) > 1:
                    issues.append(f"'Репортажная (банкеты, мероприятия)' должна быть одна в строке {i+1}")
                else:
                    single_button_rows.append(btn_text)
                    
            if "Lingerie (будуарная)" in btn_text:
                if len(row) > 1:
                    issues.append(f"'Lingerie (будуарная)' должна быть одна в строке {i+1}")
                else:
                    single_button_rows.append(btn_text)
                    
            if "Детская (школы/садики)" in btn_text:
                if len(row) > 1:
                    issues.append(f"'Детская (школы/садики)' должна быть одна в строке {i+1}")
                else:
                    single_button_rows.append(btn_text)
                    
            if "Мама с ребёнком" in btn_text:
                if len(row) > 1:
                    issues.append(f"'Мама с ребёнком' должна быть одна в строке {i+1}")
                else:
                    single_button_rows.append(btn_text)
    
    print("-" * 50)
    
    if single_button_rows:
        print("✅ Длинные кнопки размещены правильно (по одной в строке):")
        for btn in single_button_rows:
            print(f"  • {btn}")
    
    if issues:
        print(f"\n❌ Найдены проблемы с размещением ({len(issues)}):")
        for issue in issues:
            print(f"  • {issue}")
        return False
    else:
        print("\n✅ Все длинные кнопки размещены корректно!")
        
        # Проверим общий вид
        total_buttons = sum(len(row) for row in kb.inline_keyboard if not any("◀️" in btn.text or "▶️" in btn.text or "Стр" in btn.text or "Назад" in btn.text or "Новая категория" in btn.text for btn in row))
        expected_buttons = len(test_categories)
        
        if total_buttons == expected_buttons:
            print(f"✅ Все {expected_buttons} категорий отображены")
        else:
            print(f"⚠️ Отображено {total_buttons} из {expected_buttons} категорий")
        
        return True

if __name__ == "__main__":
    success = test_portfolio_keyboard_layout()
    sys.exit(0 if success else 1)