# app/bot.py
import asyncio
import os
import sys
from logging import ERROR
from pathlib import Path

# Фикс импортов при запуске как скрипт
if __package__ is None:
    project_root = str(Path(__file__).resolve().parent.parent)
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder

from app.commands import register_handlers, set_commands
from app.services.logger import QueueLogger, logger
from app.services.mongo_storage import queue_collection

load_dotenv()
TOKEN = os.getenv("TOKEN")

MAX_RETRIES = 3
RETRY_DELAY = 5


async def ensure_indexes():
    """Создаёт уникальный индекс по chat_id"""
    try:
        await queue_collection.create_index("chat_id", unique=True)
    except Exception as e:
        QueueLogger.log(action=f"Failed to create index: {e}", level=ERROR)


async def run_bot() -> None:
    """Запуск бота с retry-логикой"""
    if not TOKEN:
        logger.critical("TOKEN не найден в .env")
        return

    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            logger.info("Запуск бота...")
            await ensure_indexes()
            app = ApplicationBuilder().token(TOKEN).read_timeout(30).write_timeout(30).build()
            await set_commands(app)
            register_handlers(app)

            await app.initialize()
            await app.start()
            # Ensure polling requests include callback_query updates (some environments may restrict allowed_updates)
            allowed_updates = ["message", "callback_query", "inline_query", "my_chat_member", "chat_member"]
            await app.updater.start_polling(allowed_updates=allowed_updates)

            # Восстанавливаем планировщик автo-удаления из БД
            try:
                from app.handlers.scheduler import auto_cleanup_service

                logger.info("Восстанавление авто-удалений из БД...")
                await auto_cleanup_service.restore_all_expirations(app)
            except Exception as e:
                logger.warning(f"Не удалось восстановить авто-удаления: {e}")

            logger.info("Запуск бота завершён успешно.")
            # Держим бота живым
            stop_event = asyncio.Event()
            await stop_event.wait()

        except asyncio.CancelledError:
            logger.info("Бот остановлен")
            break

        except Exception as e:
            logger.error(f"Ошибка при запуске (попытка {attempt + 1}): {e}")
            attempt += 1
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY * (2 ** (attempt - 1))  # экспоненциальная задержка
                logger.info(f"Повторная попытка через {delay} секунд...")
                await asyncio.sleep(delay)
            else:
                logger.critical("Бот не запустился после 3 попыток")
                break

        finally:
            if "app" in locals():
                await app.updater.stop()
                await app.stop()
                await app.shutdown()


def main() -> None:
    """Синхронная обёртка для запуска"""
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")


if __name__ == "__main__":
    main()
