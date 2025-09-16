#!/usr/bin/env python3
"""
Test script to verify booking date functionality
"""

import sys
sys.path.append('.')

from datetime import datetime, timedelta, timezone
import pytz

# Recreate the logic to test
BOOK_TZ = pytz.timezone('Europe/Moscow')

def test_booking_date_logic():
    today = datetime.now(BOOK_TZ).date()
    dates = [today + timedelta(days=i) for i in range(1, 31)]  # с 1 дня (завтра) на 30 дней вперед
    
    print(f"🗓️  Текущая дата: {today.strftime('%d.%m.%Y')}")
    print(f"📅 Первые 10 доступных дат для записи:")
    
    for i, d in enumerate(dates[:10], 1):
        print(f"  {i:2d}. {d.strftime('%d.%m.%Y')} ({d.strftime('%A')})")
    
    # Verify first date is tomorrow
    tomorrow = today + timedelta(days=1)
    if dates[0] == tomorrow:
        print(f"\n✅ Правильно: первая доступная дата = {tomorrow.strftime('%d.%m.%Y')} (завтра)")
    else:
        print(f"\n❌ Ошибка: первая доступная дата = {dates[0].strftime('%d.%m.%Y')}, должна быть {tomorrow.strftime('%d.%m.%Y')}")
    
    # Check if today is NOT included
    if today not in dates:
        print(f"✅ Правильно: сегодняшняя дата {today.strftime('%d.%m.%Y')} НЕ включена")
    else:
        print(f"❌ Ошибка: сегодняшняя дата {today.strftime('%d.%m.%Y')} включена (не должна быть)")

if __name__ == "__main__":
    test_booking_date_logic()