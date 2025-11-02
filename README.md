# QueueBot

Простой Telegram‑бот для управления очередями в групповых чатах.

Основные возможности:
- Создание/удаление очередей
- Добавление/удаление/вставка/замена участников
- Отправка сообщений с inline‑клавиатурами для управления очередями

Технологии:
- Python 3.11+
- python-telegram-bot

Быстрый старт (локально, PowerShell):

1. Склонируйте репозиторий и перейдите в папку проекта

```powershell
git clone <repo-url>
cd QueueBot
```

2. Создайте виртуальное окружение и установите зависимости

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Создайте файл `.env` и добавьте TOKEN

```text
TOKEN=123456:ABC-DEF...
```

4. Запустите бота

```powershell
python -m app.bot
```

Docker

Сборка и запуск через Docker (в корне репозитория):

```powershell
docker build -t queuebot:latest .
docker run --env-file .env --restart unless-stopped queuebot:latest
```

Тесты

Запуск тестов через pytest:

```powershell
python -m pytest -q
```

