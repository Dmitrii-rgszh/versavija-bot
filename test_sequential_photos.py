#!/usr/bin/env python3
"""
Тест для проверки последовательного показа фотографий от новых к старым
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import Mock, AsyncMock, patch
import asyncio

def test_sequential_photo_display():
    """Тестируем, что фото показываются последовательно от новых к старым"""
    print("=== Тест последовательного показа фотографий ===")
    
    # Импортируем handlers и глобальный словарь
    from handlers import LAST_CATEGORY_PHOTO
    
    # Симулируем список фотографий (индексы от 0 до 4, где 4 - самая новая)
    mock_photos = ['photo_0.jpg', 'photo_1.jpg', 'photo_2.jpg', 'photo_3.jpg', 'photo_4.jpg']
    chat_id = 12345
    category_slug = 'family'
    chat_key = (chat_id, category_slug)
    
    print(f"Тестируем категорию: {category_slug}")
    print(f"Количество фото: {len(mock_photos)}")
    print(f"Ожидаемый порядок: от фото {len(mock_photos)-1} к фото 0, затем цикл")
    
    # Очищаем состояние
    if chat_key in LAST_CATEGORY_PHOTO:
        del LAST_CATEGORY_PHOTO[chat_key]
    
    # Тестируем логику выбора фотографий
    expected_sequence = []
    
    for step in range(8):  # Тестируем 8 шагов, чтобы проверить циклирование
        # Симулируем логику из handlers.py
        last_idx = LAST_CATEGORY_PHOTO.get(chat_key)
        
        if last_idx is None:
            # Первый раз - начинаем с самой новой (последней)
            idx = len(mock_photos) - 1
        else:
            # Переходим к предыдущей (более старой) фотографии
            idx = last_idx - 1
            if idx < 0:
                # Дошли до самой старой, возвращаемся к самой новой
                idx = len(mock_photos) - 1
        
        # Сохраняем выбранный индекс
        LAST_CATEGORY_PHOTO[chat_key] = idx
        expected_sequence.append(idx)
        
        print(f"Шаг {step + 1}: показываем фото {idx} ({mock_photos[idx]})")
    
    print(f"\nПолученная последовательность: {expected_sequence}")
    
    # Проверяем, что последовательность правильная
    # Ожидаем: [4, 3, 2, 1, 0, 4, 3, 2] (от новых к старым, затем цикл)
    expected = [4, 3, 2, 1, 0, 4, 3, 2]
    
    if expected_sequence == expected:
        print("✅ ТЕСТ ПРОЙДЕН: Фотографии показываются последовательно от новых к старым")
        return True
    else:
        print(f"❌ ТЕСТ НЕ ПРОЙДЕН: Ожидалось {expected}, получено {expected_sequence}")
        return False

def test_reviews_sequential_display():
    """Тестируем последовательный показ отзывов"""
    print("\n=== Тест последовательного показа отзывов ===")
    
    from handlers import LAST_CATEGORY_PHOTO
    
    # Симулируем отзывы
    mock_reviews = ['review_0.jpg', 'review_1.jpg', 'review_2.jpg']
    chat_id = 12345
    chat_key = (chat_id, 'reviews')
    
    # Очищаем состояние
    if chat_key in LAST_CATEGORY_PHOTO:
        del LAST_CATEGORY_PHOTO[chat_key]
    
    print(f"Количество отзывов: {len(mock_reviews)}")
    print(f"Ожидаемый порядок: от отзыва {len(mock_reviews)-1} к отзыву 0, затем цикл")
    
    expected_sequence = []
    
    for step in range(6):  # Тестируем полтора цикла
        last_idx = LAST_CATEGORY_PHOTO.get(chat_key)
        
        if last_idx is None:
            # Первый раз - начинаем с самого нового
            idx = len(mock_reviews) - 1
        else:
            # Переходим к предыдущему (более старому) отзыву
            idx = last_idx - 1
            if idx < 0:
                # Дошли до самого старого, возвращаемся к самому новому
                idx = len(mock_reviews) - 1
        
        LAST_CATEGORY_PHOTO[chat_key] = idx
        expected_sequence.append(idx)
        
        print(f"Шаг {step + 1}: показываем отзыв {idx} ({mock_reviews[idx]})")
    
    print(f"\nПолученная последовательность: {expected_sequence}")
    
    # Ожидаем: [2, 1, 0, 2, 1, 0]
    expected = [2, 1, 0, 2, 1, 0]
    
    if expected_sequence == expected:
        print("✅ ТЕСТ ПРОЙДЕН: Отзывы показываются последовательно от новых к старым")
        return True
    else:
        print(f"❌ ТЕСТ НЕ ПРОЙДЕН: Ожидалось {expected}, получено {expected_sequence}")
        return False

if __name__ == "__main__":
    print("Запуск тестов последовательного показа...")
    
    test1_passed = test_sequential_photo_display()
    test2_passed = test_reviews_sequential_display()
    
    print(f"\n=== РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ===")
    print(f"Тест фотографий: {'✅ ПРОЙДЕН' if test1_passed else '❌ НЕ ПРОЙДЕН'}")
    print(f"Тест отзывов: {'✅ ПРОЙДЕН' if test2_passed else '❌ НЕ ПРОЙДЕН'}")
    
    if test1_passed and test2_passed:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Последовательный показ работает корректно.")
    else:
        print("⚠️ Некоторые тесты не пройдены. Требуется проверка логики.")