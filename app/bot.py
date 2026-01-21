import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from telegram.ext import ApplicationBuilder

if __package__ is None:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

from app.commands import register_handlers, set_commands
from app.queues import queue_service
from app.services.logger import setup_logger
from app.services.mongo_storage import mongo_db

load_dotenv()

TOKEN = os.getenv("TOKEN")
MAX_RETRIES = 15
RETRY_DELAY = 5


async def start_application() -> None:
    """Основная логика запуска приложения"""

    setup_logger()
    logger.info("Инициализация бота...")

    app = ApplicationBuilder().token(TOKEN).read_timeout(30).write_timeout(30).build()

    await set_commands(app)
    register_handlers(app)
    await mongo_db.ensure_indexes()

    await app.initialize()
    await app.start()

    await app.updater.start_polling(drop_pending_updates=False)
    logger.success("Бот успешно запущен и принимает сообщения")

    try:
        logger.info("Восстановление задач авто-удаления...")
        await queue_service.auto_cleanup_service.restore_all_expirations(app)
    except Exception as e:
        logger.warning(f"Ошибка восстановления таймеров: {e}")

    # 6. Блокируем выполнение, пока не придет сигнал остановки
    # Создаем событие, которое будет ждать вечно, пока его не отменят
    stop_event = asyncio.Event()
    await stop_event.wait()


async def run_bot_with_retries() -> None:
    """Обертка для перезапуска бота при падениях"""
    if not TOKEN:
        logger.critical("Переменная окружения TOKEN не найдена!")
        return

    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            await start_application()

        except asyncio.CancelledError:
            logger.info("Получен сигнал остановки работы.")
            break

        except Exception:
            attempt += 1
            logger.exception(f"Критическая ошибка (попытка {attempt}/{MAX_RETRIES}):")

            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY * (2 ** (attempt - 1))  # Экспоненциальная задержка
                logger.warning(f"Перезапуск через {delay} секунд...")
                await asyncio.sleep(delay)
            else:
                logger.critical("Исчерпан лимит попыток перезапуска. Выход.")
                break
        finally:
            mongo_db.close()


def main() -> None:
    try:
        # На Windows иногда нужен особый Policy для EventLoop
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.run(run_bot_with_retries())

    except KeyboardInterrupt:
        # Ловим Ctrl+C в консоли, чтобы не было страшных трейсбеков
        print("\nБот остановлен пользователем (KeyboardInterrupt)")
    except Exception as e:
        print(f"\nФатальная ошибка при старте: {e}")


if __name__ == "__main__":
    main()
