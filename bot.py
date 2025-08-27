"""
Compatibility shim: keep `bot.py` as an entry point but delegate to modular package.
Original logic moved to `config.py`, `db.py`, `keyboards.py`, `handlers.py`, and `run.py`.

Running `bot.py` will import modules (register handlers) and then start the bot.
"""

from handlers import *  # registers handlers

from run import main


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
