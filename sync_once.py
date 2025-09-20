import asyncio
import logging
from simple_tracker import create_subscribers_table, sync_subscribers

logging.basicConfig(level=logging.INFO)

async def main():
    create_subscribers_table()
    await sync_subscribers()

if __name__ == '__main__':
    asyncio.run(main())
