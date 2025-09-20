#!/usr/bin/env python3
"""
Скрипт для создания пригласительной ссылки на канал/группу.
"""

import asyncio
from config import bot

# ID вашего канала
CHAT_ID = -1002553563891  # Versavija_test_group

async def create_invite_link():
    """Создает пригласительную ссылку для канала/группы"""
    try:
        # Создаем пригласительную ссылку
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHAT_ID,
            name="Основная ссылка приглашения",  # название ссылки
            expire_date=None,  # не истекает
            member_limit=None,  # без ограничения участников
            creates_join_request=False  # сразу присоединяться без запроса
        )
        
        print(f"\n{'='*60}")
        print(f"🔗 ПРИГЛАСИТЕЛЬНАЯ ССЫЛКА СОЗДАНА:")
        print(f"{'='*60}")
        print(f"Ссылка: {invite_link.invite_link}")
        print(f"Название: {invite_link.name}")
        print(f"Создатель: {invite_link.creator.full_name}")
        print(f"Основная ссылка: {'Да' if invite_link.is_primary else 'Нет'}")
        print(f"{'='*60}\n")
        
        return invite_link.invite_link
        
    except Exception as e:
        print(f"Ошибка при создании ссылки: {e}")
        
        # Попробуем получить существующую ссылку
        try:
            chat = await bot.get_chat(CHAT_ID)
            if chat.invite_link:
                print(f"\n{'='*60}")
                print(f"🔗 СУЩЕСТВУЮЩАЯ ПРИГЛАСИТЕЛЬНАЯ ССЫЛКА:")
                print(f"{'='*60}")
                print(f"Ссылка: {chat.invite_link}")
                print(f"{'='*60}\n")
                return chat.invite_link
            else:
                print("Пригласительная ссылка не найдена.")
        except Exception as e2:
            print(f"Ошибка при получении информации о чате: {e2}")
    
    finally:
        await bot.session.close()

async def main():
    print("Создание пригласительной ссылки для канала...")
    invite_link = await create_invite_link()
    
    if invite_link:
        print("✅ Готово! Можете использовать эту ссылку для приглашения участников.")
    else:
        print("❌ Не удалось получить пригласительную ссылку.")
        print("\n📝 Альтернативные способы:")
        print("1. Откройте канал в Telegram")
        print("2. Нажмите на название канала")
        print("3. Выберите 'Управление каналом'")
        print("4. В разделе 'Пригласительные ссылки' создайте новую ссылку")

if __name__ == "__main__":
    asyncio.run(main())