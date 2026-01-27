import asyncio
import os
import sys
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

MAX_RETRIES = 15
RETRY_DELAY = 5


# --- ИЗМЕНЕНИЕ: Функция принимает зависимости ---
async def start_application(app: Application, mongo_db: MongoDatabase, queue_service: QueueFacadeService) -> None:
    """Основная логика запуска приложения"""
    logger.info("Проверка индексов MongoDB...")
    await mongo_db.ensure_indexes()

    logger.info("Установка команд и регистрация обработчиков...")
    await set_commands(app)
    register_handlers(app)  # Передаем сервис в обработчики

    logger.info("Инициализация и запуск приложения Telegram...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=False)
    logger.success("Бот успешно запущен и принимает сообщения")

    try:
        logger.info("Восстановление задач авто-удаления...")
        await queue_service.auto_cleanup_service.restore_all_expirations()
    except Exception as e:
        logger.warning(f"Ошибка восстановления таймеров: {e}")

    stop_event = asyncio.Event()
    await stop_event.wait()


async def run_bot_with_retries() -> None:
    """Обертка для перезапуска бота при падениях"""
    if not TOKEN:
        logger.critical("Переменная окружения TOKEN не найдена!")
        return

    attempt = 0
    while attempt < MAX_RETRIES:
        mongo_db = None
        app = None
        try:
            mongo_db = MongoDatabase()
            await mongo_db.connect()

            await setup_logger(mongo_db)
            q_logger = QueueLogger()

            queue_repo = QueueRepository(mongo_db.db)
            scheduler = AsyncIOScheduler(timezone="UTC")
            scheduler.start()
            app = ApplicationBuilder().token(TOKEN).read_timeout(30).write_timeout(30).build()
            queue_service = QueueFacadeService(bot=app.bot, repo=queue_repo, logger=q_logger, scheduler=scheduler)
            app.bot_data["queue_service"] = queue_service

            await start_application(app, mongo_db, queue_service)

        except asyncio.CancelledError:
            logger.info("Получен сигнал остановки работы.")
            break
        except Exception:
            attempt += 1
            logger.exception(f"Критическая ошибка (попытка {attempt}/{MAX_RETRIES}):")
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY * (2 ** (attempt - 1))
                logger.warning(f"Перезапуск через {delay} секунд...")
                await asyncio.sleep(delay)
            else:
                logger.critical("Исчерпан лимит попыток перезапуска. Выход.")
                break
        finally:
            if app and app.updater and app.updater.running:
                await app.updater.stop()
            if app and app.running:
                await app.shutdown()
            if mongo_db:
                await mongo_db.close()
            if scheduler.running:
                scheduler.shutdown()
            logger.info("Ресурсы освобождены.")


def main() -> None:
    try:
        # На Windows иногда нужен особый Policy для EventLoop
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.run(run_bot_with_retries())

    except KeyboardInterrupt:
        print("\nБот остановлен пользователем (KeyboardInterrupt)")
    except Exception as e:
        print(f"\nФатальная ошибка при старте: {e}")


if __name__ == "__main__":
    main()
