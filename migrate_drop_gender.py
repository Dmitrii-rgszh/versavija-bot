import sqlite3

# WARNING: SQLite не умеет DROP COLUMN. Делаем пересоздание таблицы без gender.
# Схема целевой таблицы: user_id (PK), username, first_name, join_time, last_name, birthdate

def main():
    conn = sqlite3.connect('data.db')
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(subscribers)")
    cols = {r[1] for r in cur.fetchall()}
    if 'gender' not in cols:
        print('Поле gender уже отсутствует — миграция не требуется')
        return

    print('Начинаю миграцию: удаление колонки gender...')
    cur.execute("BEGIN TRANSACTION")
    try:
        cur.execute("""
        CREATE TABLE subscribers_new (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            join_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_name TEXT,
            birthdate TEXT
        )
        """)
        cur.execute("INSERT INTO subscribers_new (user_id, username, first_name, join_time, last_name, birthdate)\n                    SELECT user_id, username, first_name, join_time, last_name, birthdate FROM subscribers")
        cur.execute("ALTER TABLE subscribers RENAME TO subscribers_old")
        cur.execute("ALTER TABLE subscribers_new RENAME TO subscribers")
        cur.execute("DROP TABLE subscribers_old")
        conn.commit()
        print('Миграция завершена успешно')
    except Exception as e:
        conn.rollback()
        print('Ошибка миграции:', e)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
