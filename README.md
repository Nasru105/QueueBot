# QueueBot

QueueBot is a Telegram bot that helps groups run lightweight waiting lists directly inside chats. It is built on top of `python-telegram-bot` v22 and stores queues in MongoDB via `motor`, so multiple chats can share a single bot instance with persistent history.

## Features
- Multiple queues per chat with inline keyboards for joining, leaving, inserting, swapping, and renaming participants
- User-facing commands (`/create`, `/queues`, `/nickname`, `/nickname_global`) plus moderator commands (`/delete`, `/delete_all`, `/insert`, `/remove`, `/replace`, `/rename`)
- MarkdownV2-rendered queue snapshots that always reflect the latest state; outdated messages are removed automatically
- Persistent storage in MongoDB (`queue_data` and `user_data` collections) with automatic `chat_id` indexing
- JSON-formatted logging to stdout, stderr, and `data/logs/queue.log`


## Requirements
- Python 3.11 or newer
- MongoDB 5.0+ (local or hosted)
- Telegram bot token

## Local Quick Start (PowerShell)
1. Clone the repository and move into it:
   ```powershell
   git clone <repo-url>
   cd QueueBot
   ```
2. Create and activate a virtual environment, then install dependencies:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Create `.env` in the project root:
   ```text
   TOKEN=123456789:ABC-DEF...
   MONGO_URI=mongodb://localhost:27017  # optional; defaults to this value
   ```
4. Start the bot:
   ```powershell
   python -m app.bot
   ```

## Docker
Build and run from the repository root:
```powershell
docker build -t queuebot:latest .
docker run --env-file .env --restart unless-stopped queuebot:latest
```

## Testing
```powershell
python -m pytest -q
```

## Project Layout
- `app/` — bot entry point, command handlers, queue service, and infrastructure helpers
- `data/` — runtime JSON files and structured logs (`data/logs/queue.log`)
- `tests/` — pytest suite that covers commands, handlers, services, and utilities

## Configuration Notes
- `TOKEN` is required and must match your BotFather token.
- `MONGO_URI` defaults to `mongodb://localhost:27017`, but you can point it to MongoDB Atlas or any other deployment.
- Logs are written in JSON for easy ingestion; rotate or mount `data/logs` in Docker if persistence is needed.

