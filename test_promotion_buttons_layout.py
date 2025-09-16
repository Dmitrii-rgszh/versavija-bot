#!/usr/bin/env python3
"""Test promotion buttons layout - each button in separate row."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from keyboards import build_promotions_keyboard

def test_promotion_buttons_layout():
    """Test that promotion admin buttons are each in their own row."""
    print("🧪 Testing promotion buttons layout...")
    
    # Test with admin privileges
    keyboard = build_promotions_keyboard(is_admin=True, promotion_idx=0)
    
    print("\n📋 Keyboard structure:")
    for i, row in enumerate(keyboard.inline_keyboard):
        print(f"Row {i+1}: {[btn.text for btn in row]}")
    
    # Find admin buttons
    add_promotion_found = False
    delete_promotion_found = False
    add_promotion_row = -1
    delete_promotion_row = -1
    
    for i, row in enumerate(keyboard.inline_keyboard):
        for btn in row:
            if "Добавить акцию" in btn.text:
                add_promotion_found = True
                add_promotion_row = i
                print(f"✅ 'Добавить акцию' found in row {i+1}")
            elif "Удалить эту акцию" in btn.text:
                delete_promotion_found = True
                delete_promotion_row = i
                print(f"✅ 'Удалить эту акцию' found in row {i+1}")
    
    # Verify both buttons exist
    assert add_promotion_found, "❌ 'Добавить акцию' button not found!"
    assert delete_promotion_found, "❌ 'Удалить эту акцию' button not found!"
    
    # Verify they are in different rows
    assert add_promotion_row != delete_promotion_row, f"❌ Buttons are in the same row ({add_promotion_row+1})!"
    
    # Verify each button is alone in its row
    add_row = keyboard.inline_keyboard[add_promotion_row]
    delete_row = keyboard.inline_keyboard[delete_promotion_row]
    
    assert len(add_row) == 1, f"❌ 'Добавить акцию' row has {len(add_row)} buttons, expected 1!"
    assert len(delete_row) == 1, f"❌ 'Удалить эту акцию' row has {len(delete_row)} buttons, expected 1!"
    
    print(f"✅ 'Добавить акцию' is alone in row {add_promotion_row+1}")
    print(f"✅ 'Удалить эту акцию' is alone in row {delete_promotion_row+1}")
    print("🎉 All tests passed! Buttons are properly separated into different rows.")

if __name__ == "__main__":
    test_promotion_buttons_layout()