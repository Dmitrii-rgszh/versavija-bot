#!/usr/bin/env python3

import sqlite3

# Connect to database
conn = sqlite3.connect('data.db')
cursor = conn.cursor()

print("=== Clearing incorrect promotions ===")

# Delete all promotions
cursor.execute("DELETE FROM promotions;")
affected_rows = cursor.rowcount

print(f"✅ Deleted {affected_rows} incorrect promotion(s)")

conn.commit()
conn.close()

print("Database cleaned!")