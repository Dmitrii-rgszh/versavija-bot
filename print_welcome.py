import sqlite3
import pathlib
import sys

db_path = pathlib.Path(__file__).parent / 'data.db'
if not db_path.exists():
    print('<<no data.db>>')
    sys.exit(0)

conn = sqlite3.connect(str(db_path))
cur = conn.cursor()
try:
    cur.execute("SELECT value FROM settings WHERE key='welcome_text'")
    r = cur.fetchone()
    print(r[0] if r else '<<no welcome_text in DB>>')
finally:
    conn.close()
