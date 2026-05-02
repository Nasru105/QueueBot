import asyncio
import os
import sys
from datetime import timedelta, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from loguru import logger
from telegram.ext import Application, ApplicationBuilder

if __package__ is None:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

from app.commands import register_handlers, set_commands
from app.queues.queue_repository import QueueRepository
from app.queues.service import QueueFacadeService
from app.services.logger import QueueLogger, setup_logger
from app.services.mongo_storage import MongoDatabase

load_dotenv()

TOKEN = os.getenv("TOKEN")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "queue_bot_db")


# --- ИЗМЕНЕНИЕ: Функция принимает зависимости ---
async def start_application(app: Application, mongo_db: MongoDatabase, queue_service: QueueFacadeService) -> None:
    """Основная логика запуска приложения"""
    await mongo_db.ensure_indexes()

    await set_commands(app)
    register_handlers(app)

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=False)
    logger.success("Бот успешно запущен и принимает сообщения")

    try:
        await queue_service.auto_cleanup_service.restore_all_expirations()
    except Exception as e:
        logger.warning(f"Ошибка восстановления задач авто-удаления: {e}")

    stop_event = asyncio.Event()
    await stop_event.wait()


async def run_bot_with_retries() -> None:
    """Обертка для перезапуска бота при падениях"""
    if not TOKEN:
        logger.critical("Переменная окружения TOKEN не найдена!")
        return

    mongo_db = None
    app = None
    try:
        mongo_db = MongoDatabase()
        await mongo_db.connect()

        logger_level = os.getenv("LOGGER_LEVEL", "INFO")
        await setup_logger(mongo_db, logger_level)
        q_logger = QueueLogger()

        queue_repo = QueueRepository(mongo_db.db)
        scheduler = AsyncIOScheduler(timezone=timezone(timedelta(hours=3)))
        scheduler.start()
        app = ApplicationBuilder().token(TOKEN).read_timeout(30).write_timeout(30).build()
        queue_service = QueueFacadeService(bot=app.bot, repo=queue_repo, logger=q_logger, scheduler=scheduler)
        app.bot_data["queue_service"] = queue_service
        app.bot_data["scheduler"] = scheduler

        await start_application(app, mongo_db, queue_service)

    except asyncio.CancelledError:
        logger.info("Получен сигнал остановки работы.")
    except Exception as e:
        logger.exception(f"Критическая ошибка при запуске: {e}")


def main() -> None:
    try:
        asyncio.run(run_bot_with_retries())

    except KeyboardInterrupt:
        print("\nБот остановлен пользователем (KeyboardInterrupt)")
    except Exception as e:
        print(f"\nФатальная ошибка при старте: {e}")


if __name__ == "__main__":
    main()
