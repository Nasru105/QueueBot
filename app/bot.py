# app/bot.py
import asyncio
import os

from commands import register_handlers, set_commands
from dotenv import load_dotenv
from services.logger import logger
from services.mongo_storage import ensure_indexes
from telegram.ext import Application, ApplicationBuilder

# Фикс импортов при запуске как скрипт
if __package__ is None:
    import sys
    from pathlib import Path

    project_root = str(Path(__file__).resolve().parent.parent)
    sys.path.insert(0, project_root)

load_dotenv()
TOKEN = os.getenv("TOKEN")

MAX_RETRIES = 3
RETRY_DELAY = 5


async def post_init(application: Application) -> None:
    """Вызывается после инициализации Application, но до старта polling."""
    await set_commands(application)
    await ensure_indexes()
    logger.info("MongoDB: индексы созданы. Бот готов к работе.")


async def run_bot() -> None:
    """Запуск бота с retry-логикой"""
    if not TOKEN:
        logger.critical("TOKEN не найден в .env")
        return

    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            app = ApplicationBuilder().token(TOKEN).read_timeout(30).write_timeout(30).post_init(post_init).build()

            register_handlers(app)
            logger.info("Запуск бота...")

            await app.initialize()
            await app.start()
            await app.updater.start_polling()

            # Держим бота живым
            stop_event = asyncio.Event()
            await stop_event.wait()

        except asyncio.CancelledError:
            logger.info("Бот остановлен")
            break

        except Exception as e:
            logger.error(f"Ошибка при запуске (попытка {attempt + 1}): {e}", exc_info=True)
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
