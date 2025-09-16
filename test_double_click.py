#!/usr/bin/env python3
"""Test anti-double-click protection"""
import time

# Симуляция защиты от двойного клика
ACTIVE_CALLBACKS = {}
CALLBACK_COOLDOWN = 1.0

def test_double_click_protection(user_id: int, callback_data: str) -> bool:
    """
    Test function for double-click protection
    Returns True if callback should be processed, False if should be ignored
    """
    global ACTIVE_CALLBACKS
    callback_key = f"{user_id}:{callback_data}"
    current_time = time.time()
    
    if callback_key in ACTIVE_CALLBACKS:
        time_since_last = current_time - ACTIVE_CALLBACKS[callback_key]
        if time_since_last < CALLBACK_COOLDOWN:
            print(f"❌ BLOCKED: Double-click from user {user_id}, data={callback_data} (%.2fs since last)" % time_since_last)
            return False
    
    # Update last callback time
    ACTIVE_CALLBACKS[callback_key] = current_time
    
    # Clean up old entries (older than 10 seconds)
    cutoff_time = current_time - 10.0
    ACTIVE_CALLBACKS = {k: v for k, v in ACTIVE_CALLBACKS.items() if v > cutoff_time}
    
    print(f"✅ ALLOWED: Callback from user {user_id}, data={callback_data}")
    return True

# Test cases
print("=== Testing Anti-Double-Click Protection ===\n")

# Test 1: First click should be allowed
print("Test 1: First click")
test_double_click_protection(123, "wedding_pkg_next:1")

# Test 2: Immediate second click should be blocked
print("\nTest 2: Immediate second click (should be blocked)")
test_double_click_protection(123, "wedding_pkg_next:1")

# Test 3: Different user, same action - should be allowed
print("\nTest 3: Different user, same action")
test_double_click_protection(456, "wedding_pkg_next:1")

# Test 4: Same user, different action - should be allowed
print("\nTest 4: Same user, different action")
test_double_click_protection(123, "wedding_pkg_prev:1")

# Test 5: Wait for cooldown, then retry
print("\nTest 5: Wait for cooldown...")
time.sleep(1.1)  # Wait longer than cooldown
test_double_click_protection(123, "wedding_pkg_next:1")

print("\n=== Test completed ===")
