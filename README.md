# Versavija Telegram Bot

Телеграм бот (Aiogram) с меню, портфолио, записями и админскими функциями.

## Локальный запуск

1. Создайте `.env` (пример):
```
BOT_TOKEN=XXXXXXXXX:YYYYYYYYYYYYYYYY
ADMIN_IDS=5607311019,669501992
```
2. Установите зависимости:
```
pip install -r requirements.txt
```
3. Запуск:
```
python run.py
```

## Docker (локально)
```
docker build -t versavija-bot:latest .
docker run -d --name versavija-bot \
  -e BOT_TOKEN=XXXXXXXXX:YYYY \
  -e ADMIN_IDS=5607311019,669501992 \
  -e DB_PATH=/data/data.db \
  -v $(pwd)/data:/data \
  versavija-bot:latest
```

## Docker Compose (сервер)
1. Создайте файл `.env` рядом с `docker-compose.yml` (НЕ коммитить в публичный репозиторий):
```
BOT_TOKEN=XXXXXXXXX:YYYY
ADMIN_IDS=5607311019,669501992
DOCKER_HUB_IMAGE=<login>/versavija-bot:latest
```
2. Запуск:
```
docker compose up -d
```
Файл `.env` не копируется в образ, но переменные становятся доступными внутри контейнера через окружение, а код (load_dotenv + os.getenv) их видит.

Если хотите смонтировать сам файл внутрь контейнера (обычно не нужно) — раскомментируйте соответствующую строку в `docker-compose.yml`.

## Обновление образа на сервере
```
docker pull <login>/versavija-bot:latest
docker compose up -d
```

## Автодеплой скриптами

PowerShell (Windows):
```
./deploy.ps1 -Repo <login>/versavija-bot -RemoteHost 176.108.245.116 -BotToken "XXXX:YYYY" -AdminIds "5607311019,669501992"
```

Linux / macOS:
```
chmod +x deploy.sh
./deploy.sh -r <login>/versavija-bot -h 176.108.245.116 -k "XXXX:YYYY" -a "5607311019,669501992"
```

Скрипты:
1. Сбирают образ
2. (Опционально) docker login
3. Публикуют образ
4. Создают временный `.env` (токен не сохраняется в репозитории)
5. Копируют файлы на сервер
6. Выполняют `docker compose up -d`
7. Показывают хвост логов

Токен не попадает в git, только передаётся напрямую.

## Переменные окружения
- BOT_TOKEN – токен Telegram бота
- ADMIN_IDS – список admin ID (через запятую)
- DB_PATH – путь к sqlite (по умолчанию /app/data.db внутри контейнера)

## Healthcheck
В Dockerfile реализован простой healthcheck (sqlite доступна).

## Backup БД
```
docker cp versavija-bot:/data/data.db ./data_backup.db
```

## Лицензия
Private
