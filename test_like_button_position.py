#!/usr/bin/env python3
"""Test like button positioned between navigation arrows."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from keyboards import build_category_photo_nav_keyboard

def test_like_button_position():
    """Test that like button is positioned between navigation arrows."""
    print("🧪 Testing like button position between arrows...")
    
    # Test data
    category_slug = "family"
    photo_index = 0
    user_id = 123456
    likes_count = 5
    user_has_liked = False
    
    # Build keyboard
    keyboard = build_category_photo_nav_keyboard(category_slug, photo_index, user_id, likes_count, user_has_liked)
    
    print(f"\n📋 Keyboard structure:")
    for i, row in enumerate(keyboard.inline_keyboard):
        row_texts = [btn.text for btn in row]
        row_callbacks = [btn.callback_data for btn in row]
        print(f"Row {i+1}: {row_texts}")
        print(f"       Callbacks: {row_callbacks}")
    
    # Validate first row has 3 buttons: ◀️, ❤️ X, ▶️
    first_row = keyboard.inline_keyboard[0]
    assert len(first_row) == 3, f"First row should have 3 buttons, got {len(first_row)}"
    
    # Check button positions
    left_arrow = first_row[0]
    like_button = first_row[1]
    right_arrow = first_row[2]
    
    print(f"\n🔍 Button analysis:")
    print(f"   Left button: '{left_arrow.text}' -> {left_arrow.callback_data}")
    print(f"   Middle button: '{like_button.text}' -> {like_button.callback_data}")
    print(f"   Right button: '{right_arrow.text}' -> {right_arrow.callback_data}")
    
    # Validate button content
    assert left_arrow.text == "◀️", f"Left button should be '◀️', got '{left_arrow.text}'"
    assert "❤️" in like_button.text, f"Middle button should contain '❤️', got '{like_button.text}'"
    assert str(likes_count) in like_button.text, f"Middle button should show likes count {likes_count}, got '{like_button.text}'"
    assert right_arrow.text == "▶️", f"Right button should be '▶️', got '{right_arrow.text}'"
    
    # Validate callbacks
    assert left_arrow.callback_data == f"pf_pic:{category_slug}:{photo_index}"
    assert like_button.callback_data == f"like:{category_slug}:{photo_index}"
    assert right_arrow.callback_data == f"pf_pic:{category_slug}:{photo_index}"
    
    print(f"✅ Perfect! Like button is positioned between arrows: ◀️ ❤️ {likes_count} ▶️")
    
    # Test second row (back button)
    second_row = keyboard.inline_keyboard[1]
    assert len(second_row) == 1, f"Second row should have 1 button, got {len(second_row)}"
    assert second_row[0].text == "⬅️ Категории", f"Back button text incorrect: {second_row[0].text}"
    print(f"✅ Back button is correctly positioned in second row")
    
    # Test without user_id (should only show arrows)
    keyboard_no_user = build_category_photo_nav_keyboard(category_slug, photo_index)
    first_row_no_user = keyboard_no_user.inline_keyboard[0]
    assert len(first_row_no_user) == 2, f"Without user_id, first row should have 2 buttons, got {len(first_row_no_user)}"
    assert first_row_no_user[0].text == "◀️"
    assert first_row_no_user[1].text == "▶️"
    print(f"✅ Without user_id, only arrows are shown: ◀️ ▶️")
    
    print(f"\n🎉 All position tests passed!")
    return True

if __name__ == "__main__":
    try:
        success = test_like_button_position()
        print(f"\n{'🎉 SUCCESS' if success else '❌ FAILURE'}: Like button position test completed")
    except Exception as e:
        print(f"\n❌ ERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)