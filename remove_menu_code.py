#!/usr/bin/env python3
"""
Скрипт для удаления блоков кода управления меню из handlers.py
"""

def remove_menu_management_code():
    """Удаляет код управления меню из handlers.py"""
    
    with open('handlers.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    skip_block = False
    block_depth = 0
    
    for i, line in enumerate(lines):
        # Проверяем начало блоков для удаления
        if '# edit/delete menu handlers' in line:
            skip_block = True
            print(f"Начало удаления с строки {i+1}: {line.strip()}")
            continue
        elif skip_block and 'if data == \'admin_broadcast\':' in line:
            skip_block = False
            print(f"Конец удаления на строке {i+1}: {line.strip()}")
            new_lines.append(line)
            continue
        
        # Удаляем обработчики в текстовых сообщениях
        if 'if a == \'edit_menu\':' in line:
            skip_block = True
            print(f"Удаляем edit_menu handler с строки {i+1}")
            continue
        elif skip_block and line.strip().startswith('if a == ') and 'edit_menu' not in line:
            skip_block = False
            new_lines.append(line)
            continue
            
        if not skip_block:
            new_lines.append(line)
    
    # Записываем обновленный файл
    with open('handlers.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"✅ Удалено {len(lines) - len(new_lines)} строк")
    print(f"Было строк: {len(lines)}, стало: {len(new_lines)}")

if __name__ == "__main__":
    remove_menu_management_code()