#!/usr/bin/env python3
"""
Тест для проверки исправления обработчика удаления акций.
Убеждается, что код не пытается редактировать сообщение без текста.
"""

import os
import sys

def test_promotion_deletion_fix():
    """Проверяет, что обработчик удаления акций использует answer вместо edit_text"""
    
    handlers_file = "handlers.py"
    if not os.path.exists(handlers_file):
        print(f"❌ Файл {handlers_file} не найден")
        return False
    
    with open(handlers_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("🔍 Проверяем исправление обработчика удаления акций...")
    
    issues = []
    
    # Найдем блок обработчика delete_promotion
    if "if data.startswith('delete_promotion:'):" in content:
        # Найдем индекс начала блока
        start_pos = content.find("if data.startswith('delete_promotion:'):")
        if start_pos == -1:
            issues.append("❌ Не найден обработчик delete_promotion")
        else:
            # Возьмем блок кода после этого условия (примерно 1000 символов)
            block = content[start_pos:start_pos + 1500]
            
            # Проверим, что используется answer, а не edit_text
            if "query.message.edit_text(" in block:
                issues.append("❌ Все еще используется query.message.edit_text() в delete_promotion")
            elif "query.message.answer(" in block:
                print("✅ Используется query.message.answer() вместо edit_text")
            else:
                issues.append("❌ Не найдено query.message.answer() в delete_promotion")
            
            # Проверим, что есть подтверждение удаления
            if "Подтверждение удаления" in block:
                print("✅ Найден текст подтверждения удаления")
            else:
                issues.append("❌ Отсутствует текст подтверждения удаления")
            
            # Проверим, что есть кнопки подтверждения
            if "confirm_delete_promotion:" in block:
                print("✅ Найдены кнопки подтверждения удаления")
            else:
                issues.append("❌ Отсутствуют кнопки подтверждения")
    else:
        issues.append("❌ Не найден обработчик delete_promotion")
    
    print("-" * 50)
    
    if issues:
        print(f"❌ Найдены проблемы ({len(issues)}):")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("✅ Обработчик удаления акций исправлен корректно!")
        print("✅ Теперь не будет ошибки 'there is no text in the message to edit'")
        return True

if __name__ == "__main__":
    success = test_promotion_deletion_fix()
    sys.exit(0 if success else 1)