#!/usr/bin/env python3
"""Test photo likes functionality with clean data."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import sqlite3
from pathlib import Path
from db import init_db, toggle_photo_like, get_photo_likes_count, user_has_liked_photo, DB_PATH
from keyboards import build_category_photo_nav_keyboard

def clear_test_likes():
    """Clear all likes from test database."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('DELETE FROM photo_likes')
    con.commit()
    con.close()

def test_photo_likes_system():
    """Test the complete photo likes system."""
    print("🧪 Testing photo likes system with red heart...")
    
    # Initialize database and clear test data
    init_db()
    clear_test_likes()
    print("✅ Database initialized and test data cleared")
    
    # Test data
    category_slug = "family"
    photo_index = 0
    user_id_1 = 123456
    user_id_2 = 789012
    
    print(f"\n📝 Testing with category '{category_slug}', photo index {photo_index}")
    
    # Test 1: Initial state - no likes
    likes_count = get_photo_likes_count(category_slug, photo_index)
    user1_liked = user_has_liked_photo(category_slug, photo_index, user_id_1)
    user2_liked = user_has_liked_photo(category_slug, photo_index, user_id_2)
    
    print(f"📊 Initial state:")
    print(f"   Likes count: {likes_count}")
    print(f"   User 1 has liked: {user1_liked}")
    print(f"   User 2 has liked: {user2_liked}")
    
    assert likes_count == 0, f"Expected 0 likes initially, got {likes_count}"
    assert not user1_liked, "User 1 should not have liked initially"
    assert not user2_liked, "User 2 should not have liked initially"
    print("✅ Initial state correct")
    
    # Test 2: User 1 likes photo
    print(f"\n👤 User 1 likes photo...")
    added = toggle_photo_like(category_slug, photo_index, user_id_1)
    likes_count = get_photo_likes_count(category_slug, photo_index)
    user1_liked = user_has_liked_photo(category_slug, photo_index, user_id_1)
    user2_liked = user_has_liked_photo(category_slug, photo_index, user_id_2)
    
    print(f"📊 After User 1 like:")
    print(f"   Like added: {added}")
    print(f"   Likes count: {likes_count}")
    print(f"   User 1 has liked: {user1_liked}")
    print(f"   User 2 has liked: {user2_liked}")
    
    assert added == True, "Like should have been added"
    assert likes_count == 1, f"Expected 1 like, got {likes_count}"
    assert user1_liked == True, "User 1 should have liked"
    assert user2_liked == False, "User 2 should still not have liked"
    print("✅ User 1 like added successfully")
    
    # Test 3: User 2 likes photo
    print(f"\n👤 User 2 likes photo...")
    added = toggle_photo_like(category_slug, photo_index, user_id_2)
    likes_count = get_photo_likes_count(category_slug, photo_index)
    user1_liked = user_has_liked_photo(category_slug, photo_index, user_id_1)
    user2_liked = user_has_liked_photo(category_slug, photo_index, user_id_2)
    
    print(f"📊 After User 2 like:")
    print(f"   Like added: {added}")
    print(f"   Likes count: {likes_count}")
    print(f"   User 1 has liked: {user1_liked}")
    print(f"   User 2 has liked: {user2_liked}")
    
    assert added == True, "Like should have been added"
    assert likes_count == 2, f"Expected 2 likes, got {likes_count}"
    assert user1_liked == True, "User 1 should still have liked"
    assert user2_liked == True, "User 2 should now have liked"
    print("✅ User 2 like added successfully")
    
    # Test 4: Test keyboard generation with red hearts
    print(f"\n⌨️ Testing keyboard generation with red hearts...")
    
    # For user 1 (has liked)
    kb1 = build_category_photo_nav_keyboard(category_slug, photo_index, user_id_1, likes_count, user1_liked)
    like_button_1 = kb1.inline_keyboard[0][0]  # First row, first button
    print(f"   User 1 button text: '{like_button_1.text}'")
    print(f"   User 1 callback: '{like_button_1.callback_data}'")
    
    # For user 2 (has liked)
    kb2 = build_category_photo_nav_keyboard(category_slug, photo_index, user_id_2, likes_count, user2_liked)
    like_button_2 = kb2.inline_keyboard[0][0]  # First row, first button
    print(f"   User 2 button text: '{like_button_2.text}'")
    print(f"   User 2 callback: '{like_button_2.callback_data}'")
    
    # Validate button content - both should show red heart regardless of like status
    assert "❤️ 2" in like_button_1.text, f"User 1 button should show '❤️ 2', got '{like_button_1.text}'"
    assert "❤️ 2" in like_button_2.text, f"User 2 button should also show '❤️ 2', got '{like_button_2.text}'"
    assert like_button_1.callback_data == f"like:{category_slug}:{photo_index}"
    assert like_button_2.callback_data == f"like:{category_slug}:{photo_index}"
    print("✅ Keyboard generation working correctly - both users see red heart ❤️")
    
    # Test 5: User 1 unlikes photo
    print(f"\n💔 User 1 unlikes photo...")
    removed = toggle_photo_like(category_slug, photo_index, user_id_1)
    likes_count = get_photo_likes_count(category_slug, photo_index)
    user1_liked = user_has_liked_photo(category_slug, photo_index, user_id_1)
    user2_liked = user_has_liked_photo(category_slug, photo_index, user_id_2)
    
    print(f"📊 After User 1 unlike:")
    print(f"   Like removed: {not removed}")
    print(f"   Likes count: {likes_count}")
    print(f"   User 1 has liked: {user1_liked}")
    print(f"   User 2 has liked: {user2_liked}")
    
    assert removed == False, "Like should have been removed"
    assert likes_count == 1, f"Expected 1 like, got {likes_count}"
    assert user1_liked == False, "User 1 should no longer have liked"
    assert user2_liked == True, "User 2 should still have liked"
    
    # Test keyboard after unlike - still red heart
    kb_after_unlike = build_category_photo_nav_keyboard(category_slug, photo_index, user_id_1, likes_count, user1_liked)
    button_after_unlike = kb_after_unlike.inline_keyboard[0][0]
    print(f"   User 1 button after unlike: '{button_after_unlike.text}'")
    assert "❤️ 1" in button_after_unlike.text, f"Button should still show red heart '❤️ 1', got '{button_after_unlike.text}'"
    print("✅ User 1 like removed successfully, still shows red heart")
    
    # Test 6: Different photo should have separate likes
    print(f"\n📸 Testing different photo...")
    photo_index_2 = 1
    likes_count_2 = get_photo_likes_count(category_slug, photo_index_2)
    print(f"   Photo {photo_index_2} likes count: {likes_count_2}")
    
    assert likes_count_2 == 0, f"Different photo should have 0 likes, got {likes_count_2}"
    print("✅ Different photos have separate like counts")
    
    print(f"\n🎉 All photo likes tests passed with red heart display!")
    return True

if __name__ == "__main__":
    try:
        success = test_photo_likes_system()
        print(f"\n{'🎉 SUCCESS' if success else '❌ FAILURE'}: Photo likes system test completed")
    except Exception as e:
        print(f"\n❌ ERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)