#!/usr/bin/env python3
"""Test that admin promotion message doesn't contain instructional text."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_admin_promotion_messages():
    """Test that admin promotion messages don't contain instructional text."""
    print("🧪 Testing admin promotion message content...")
    
    # Read handlers.py and check for the unwanted text
    with open('handlers.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    unwanted_text = "Как администратор, вы можете добавить новую акцию:"
    
    # Count occurrences
    count = content.count(unwanted_text)
    
    print(f"📋 Searching for: '{unwanted_text}'")
    print(f"🔍 Found {count} occurrences")
    
    if count == 0:
        print("✅ Success! Unwanted text has been removed from all locations.")
    else:
        print(f"❌ Error! Found {count} occurrences of unwanted text.")
        
        # Find line numbers where it appears
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if unwanted_text in line:
                print(f"   Line {i}: {line.strip()}")
    
    # Also check that the basic promotion messages still exist
    basic_message = "🎉 На текущий момент нет действующих акций. Мы работаем над этим! 😊"
    basic_count = content.count(basic_message)
    
    print(f"\n📋 Checking basic message: '{basic_message[:50]}...'")
    print(f"🔍 Found {basic_count} occurrences")
    
    if basic_count > 0:
        print("✅ Basic promotion message is still present.")
    else:
        print("❌ Warning! Basic promotion message not found.")
    
    return count == 0

if __name__ == "__main__":
    success = test_admin_promotion_messages()
    print(f"\n🎉 Test {'PASSED' if success else 'FAILED'}!")