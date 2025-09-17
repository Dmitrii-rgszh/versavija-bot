import asyncio
from telethon import TelegramClient
from getpass import getpass

API_ID = 21700254
API_HASH = "5d82759692cfedc1170598a5d5cd2ad9"
SESSION_NAME = "subscriber_tracker_tl"
PHONE_NUMBER = "+79170386777"
PASSWORD_2FA = "Miron975864...!!!"

async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("[TL] Авторизация требуется. Будет отправлен код в Telegram.")
        await client.send_code_request(PHONE_NUMBER)
        code = input("Введите код из Telegram: ").strip()
        try:
            await client.sign_in(PHONE_NUMBER, code)
        except Exception as e:
            if 'password' in str(e).lower():
                print("Требуется пароль 2FA")
                await client.sign_in(password=PASSWORD_2FA)
            else:
                raise
    print("[TL] Авторизация Telethon выполнена.")
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
