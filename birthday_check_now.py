import asyncio
import argparse
from datetime import datetime, timedelta, date

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from birthday_scheduler import _send_channel_congrats_for, _send_dm_promos_for
from config import bot


def _now_msk() -> datetime:
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo('Europe/Moscow'))
        except Exception:
            pass
    return datetime.utcnow() + timedelta(hours=3)


async def main():
    parser = argparse.ArgumentParser(description='Run birthday checks immediately (channel congrats + DM promos).')
    parser.add_argument('--date', help='Date in YYYY-MM-DD (MSK). Default: today MSK', default=None)
    args = parser.parse_args()

    if args.date:
        y, m, d = map(int, args.date.split('-'))
        target = date(y, m, d)
    else:
        target = _now_msk().date()

    # Run both checks for the target day
    await _send_channel_congrats_for(target)
    await _send_dm_promos_for(target)
    try:
        await bot.session.close()
    except Exception:
        pass


if __name__ == '__main__':
    asyncio.run(main())
