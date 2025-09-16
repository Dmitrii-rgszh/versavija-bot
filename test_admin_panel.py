#!/usr/bin/env python3
"""
Тест для проверки упрощенной админ-панели.
Должны остаться только кнопка рассылки и переключение режима администратора.
"""

import sys
import os

# Add the current directory to Python path to import modules
sys.path.insert(0, os.getcwd())

from keyboards import admin_panel_keyboard

def test_simplified_admin_panel():
    """Проверяет, что админ-панель содержит только нужные кнопки"""
    
    print("🔍 Тестируем упрощенную админ-панель...")
    
    # Тестируем админ-панель без переключения режима
    kb_no_toggle = admin_panel_keyboard()
    
    print(f"\n📋 Админ-панель без переключения режима ({len(kb_no_toggle.inline_keyboard)} строк):")
    for i, row in enumerate(kb_no_toggle.inline_keyboard):
        row_texts = [btn.text for btn in row]
        print(f"  Строка {i+1}: {row_texts}")
    
    # Тестируем админ-панель с переключением режима
    kb_with_toggle = admin_panel_keyboard(admin_mode_on=True)
    
    print(f"\n📋 Админ-панель с переключением режима ({len(kb_with_toggle.inline_keyboard)} строк):")
    for i, row in enumerate(kb_with_toggle.inline_keyboard):
        row_texts = [btn.text for btn in row]
        print(f"  Строка {i+1}: {row_texts}")
    
    # Проверяем содержимое
    removed_buttons = [
        "Изменить картинку приветствия",
        "Управление меню", 
        "Просмотреть структуру меню"
    ]
    
    expected_buttons = [
        "📢 Рассылка сообщений"
    ]
    
    all_buttons_no_toggle = [btn.text for row in kb_no_toggle.inline_keyboard for btn in row]
    all_buttons_with_toggle = [btn.text for row in kb_with_toggle.inline_keyboard for btn in row]
    
    issues = []
    
    # Проверяем, что удаленные кнопки отсутствуют
    for removed_btn in removed_buttons:
        if any(removed_btn in btn for btn in all_buttons_no_toggle):
            issues.append(f"❌ Найдена удаленная кнопка: '{removed_btn}' (без переключения)")
        if any(removed_btn in btn for btn in all_buttons_with_toggle):
            issues.append(f"❌ Найдена удаленная кнопка: '{removed_btn}' (с переключением)")
    
    # Проверяем, что нужные кнопки присутствуют
    for expected_btn in expected_buttons:
        if not any(expected_btn in btn for btn in all_buttons_no_toggle):
            issues.append(f"❌ Отсутствует ожидаемая кнопка: '{expected_btn}' (без переключения)")
        if not any(expected_btn in btn for btn in all_buttons_with_toggle):
            issues.append(f"❌ Отсутствует ожидаемая кнопка: '{expected_btn}' (с переключением)")
    
    # Проверяем переключение режима
    admin_mode_buttons = [btn for btn in all_buttons_with_toggle if "Режим администратора" in btn]
    if not admin_mode_buttons:
        issues.append("❌ Отсутствует кнопка переключения режима администратора")
    
    print("\n" + "="*50)
    
    if issues:
        print(f"❌ Найдены проблемы ({len(issues)}):")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("✅ Админ-панель упрощена корректно!")
        print(f"✅ Присутствуют все ожидаемые кнопки: {expected_buttons}")
        print(f"✅ Удалены все ненужные кнопки: {removed_buttons}")
        print("✅ Кнопка переключения режима администратора работает")
        return True

if __name__ == "__main__":
    success = test_simplified_admin_panel()
    sys.exit(0 if success else 1)