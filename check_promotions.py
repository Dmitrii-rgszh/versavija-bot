#!/usr/bin/env python3

import sqlite3
from datetime import datetime

# Connect to database
conn = sqlite3.connect('data.db')
cursor = conn.cursor()

print("=== Checking promotions table ===")

# Check if promotions table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='promotions';")
table_exists = cursor.fetchone()

if not table_exists:
    print("❌ Table 'promotions' does not exist!")
    conn.close()
    exit(1)

print("✅ Table 'promotions' exists")

# Get table schema
cursor.execute("PRAGMA table_info(promotions);")
columns = cursor.fetchall()
print(f"📋 Table schema:")
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

# Get all promotions
cursor.execute("SELECT * FROM promotions;")
promotions = cursor.fetchall()

print(f"\n📊 Total promotions in database: {len(promotions)}")

if promotions:
    print("\n🎉 Promotions found:")
    for i, promo in enumerate(promotions, 1):
        print(f"\n--- Promotion #{i} ---")
        print(f"ID: {promo[0]}")
        print(f"Title: {promo[1]}")
        print(f"Description: {promo[2]}")
        print(f"Image ID: {promo[3]}")
        print(f"Start Date: {promo[4]}")
        print(f"End Date: {promo[5]}")
        print(f"Created By: {promo[6]}")
        print(f"Created At: {promo[7]}")
        
        # Check if promotion is currently active
        today = datetime.now().strftime('%Y-%m-%d')
        if promo[4] <= today <= promo[5]:
            print("🟢 Status: ACTIVE")
        elif promo[4] > today:
            print("🟡 Status: FUTURE")
        else:
            print("🔴 Status: EXPIRED")
else:
    print("❌ No promotions found in database")

conn.close()