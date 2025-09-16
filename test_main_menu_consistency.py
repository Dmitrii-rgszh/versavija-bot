#!/usr/bin/env python3
"""
Тест для проверки единообразия текста главного меню во всем коде.
Все места, где отправляется главное меню, должны использовать MENU_MESSAGES["main"]
"""

import re
import sys
import os

def test_main_menu_consistency():
    """Проверяет, что все возвраты в главное меню используют единый текст"""
    
    handlers_file = "handlers.py"
    if not os.path.exists(handlers_file):
        print(f"❌ Файл {handlers_file} не найден")
        return False
    
    with open(handlers_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Найдем определение MENU_MESSAGES["main"]
    menu_messages_match = re.search(r'MENU_MESSAGES\s*=\s*{[^}]*"main":\s*"([^"]*)"', content, re.DOTALL)
    if not menu_messages_match:
        print("❌ Не найден MENU_MESSAGES['main']")
        return False
    
    expected_text = menu_messages_match.group(1)
    print(f"✅ Ожидаемый текст главного меню: '{expected_text}'")
    
    # Проверим все строки кода, которые отправляют главное меню
    issues = []
    
    # Поиск всех мест где используется reply_markup с главным меню
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        # Пропускаем комментарии и строки с MENU_MESSAGES
        if line.strip().startswith('#') or 'MENU_MESSAGES["main"]' in line or 'MENU_MESSAGES[\'main\']' in line:
            continue
        
        # Ищем места где отправляется сообщение с главным меню
        if 'reply_markup=kb' in line or 'reply_markup=kb_main' in line:
            # Проверим предыдущие несколько строк на наличие build_main_keyboard
            context_start = max(0, i-10)
            context_lines = lines[context_start:i+1]
            context = '\n'.join(context_lines)
            
            if 'build_main_keyboard' in context:
                # Проверим текст в этой строке
                if '.answer(' in line or '.send_message(' in line:
                    # Извлечем текст между кавычками
                    text_match = re.search(r'[\'"]([^\'"]*)[\'"]', line)
                    if text_match:
                        actual_text = text_match.group(1)
                        if actual_text != expected_text and actual_text not in ['', ' ']:
                            issues.append({
                                'line': i,
                                'actual': actual_text,
                                'expected': expected_text,
                                'code': line.strip()
                            })
    
    # Также проверим использование MENU_MESSAGES
    correct_usage = content.count('MENU_MESSAGES["main"]') + content.count("MENU_MESSAGES['main']")
    print(f"✅ Найдено {correct_usage} корректных использований MENU_MESSAGES['main']")
    
    if issues:
        print(f"\n❌ Найдены несоответствия ({len(issues)}):")
        for issue in issues:
            print(f"  Строка {issue['line']}: '{issue['actual']}' != '{issue['expected']}'")
            print(f"    Код: {issue['code']}")
        return False
    else:
        print("✅ Все тексты главного меню единообразны!")
        return True

if __name__ == "__main__":
    success = test_main_menu_consistency()
    sys.exit(0 if success else 1)