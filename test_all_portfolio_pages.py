#!/usr/bin/env python3
"""
Расширенный тест для проверки размещения кнопок портфолио на всех страницах.
"""

import sys
import os

# Add the current directory to Python path to import modules
sys.path.insert(0, os.getcwd())

from keyboards import build_portfolio_keyboard

def test_all_portfolio_pages():
    """Проверяет размещение кнопок на всех страницах портфолио"""
    
    # Полный список категорий (как в реальном коде)
    all_categories = [
        {"text": "👨‍👩‍👧‍👦 Семейная", "slug": "family"},
        {"text": "💕 Love Story", "slug": "love_story"},
        {"text": "👤 Индивидуальная", "slug": "personal"},
        {"text": "🎉 Репортажная (банкеты, мероприятия)", "slug": "reportage"},  # Длинная
        {"text": "💍 Свадебная", "slug": "wedding"},
        {"text": "💋 Lingerie (будуарная)", "slug": "lingerie"},  # Длинная
        {"text": "👶 Детская (школы/садики)", "slug": "children"},  # Длинная
        {"text": "👩‍👶 Мама с ребёнком", "slug": "mom_child"},  # Длинная
        {"text": "✝️ Крещение", "slug": "baptism"},
        {"text": "⛪ Венчание", "slug": "wedding_church"},
    ]
    
    page_size = 6
    total_pages = (len(all_categories) + page_size - 1) // page_size  # Округление вверх
    
    print(f"🔍 Анализ размещения кнопок портфолио на всех {total_pages} страницах:")
    print("=" * 60)
    
    all_issues = []
    all_single_button_rows = []
    total_buttons_checked = 0
    
    for page in range(total_pages):
        print(f"\n📄 СТРАНИЦА {page + 1}:")
        print("-" * 50)
        
        kb = build_portfolio_keyboard(all_categories, page=page, is_admin=False)
        
        for i, row in enumerate(kb.inline_keyboard):
            # Пропускаем навигационные кнопки и кнопку "Назад"
            if any(btn_text in row[0].text for btn_text in ["◀️", "▶️", "Стр", "⬅️ Назад", "Новая категория"]):
                continue
                
            row_texts = [btn.text for btn in row]
            total_buttons_checked += len(row)
            
            print(f"Строка {i+1}: {len(row)} кнопок - {row_texts}")
            
            # Проверяем все длинные кнопки
            long_categories_to_check = [
                "Репортажная (банкеты, мероприятия)",
                "Lingerie (будуарная)",
                "Детская (школы/садики)",
                "Мама с ребёнком"
            ]
            
            for btn_text in row_texts:
                for long_cat in long_categories_to_check:
                    if long_cat in btn_text:
                        if len(row) > 1:
                            all_issues.append(f"'{long_cat}' должна быть одна в строке (страница {page+1}, строка {i+1})")
                        else:
                            all_single_button_rows.append(f"{btn_text} (страница {page+1})")
    
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    
    if all_single_button_rows:
        print(f"\n✅ Длинные кнопки размещены правильно ({len(all_single_button_rows)}):")
        for btn in all_single_button_rows:
            print(f"  • {btn}")
    
    if all_issues:
        print(f"\n❌ Найдены проблемы с размещением ({len(all_issues)}):")
        for issue in all_issues:
            print(f"  • {issue}")
        return False
    else:
        print(f"\n✅ Все длинные кнопки размещены корректно!")
        print(f"✅ Проверено кнопок категорий: {total_buttons_checked}")
        print(f"✅ Общее количество категорий: {len(all_categories)}")
        return True

if __name__ == "__main__":
    success = test_all_portfolio_pages()
    sys.exit(0 if success else 1)