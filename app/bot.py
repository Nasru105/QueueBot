import os
import time

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder

# If the module is executed directly (python app/bot.py), the package
# imports like `from app.commands` will fail because the parent package
# isn't on sys.path. In that case, add the project root to sys.path so
# absolute package imports keep working. Prefer `python -m app.bot`.
if __package__ is None:
    import sys
    from pathlib import Path

    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from app.commands import register_handlers, set_commands
from app.services.logger import logger

load_dotenv()
TOKEN = os.getenv("TOKEN")

MAX_RETRIES = 3
RETRY_DELAY = 5  # секунд между попытками


def main():
    if not TOKEN:
        logger.critical(
            "Токен бота не найден! Убедитесь, что файл .env существует и содержит TOKEN."
        )
        return

    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            app = (
                ApplicationBuilder()
                .token(TOKEN)
                .read_timeout(30)
                .write_timeout(30)
                .post_init(set_commands)
                .build()
            )
            register_handlers(app)
            logger.info("Бот запущен.")

            app.run_polling()
            # Если бот завершился корректно, выходим из цикла
            logger.info("Бот завершил свою работу")
            break

        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.warning("Игнорируем ошибку 'Event loop is closed'")
            else:
                logger.error(f"RuntimeError: {e}", exc_info=True)
                attempt += 1
                if attempt < MAX_RETRIES:
                    logger.info(f"Попытка {attempt + 1} через {RETRY_DELAY} секунд...")
                    time.sleep(RETRY_DELAY)

        except ConnectionError as ce:
            logger.error(f"Ошибка подключения: {ce}", exc_info=True)
            attempt += 1
            if attempt < MAX_RETRIES:
                logger.info(f"Попытка {attempt + 1} через {RETRY_DELAY} секунд...")
                time.sleep(RETRY_DELAY * 2)  # Увеличиваем задержку для сетевых ошибок

        except Exception as ex:
            logger.error(f"Критическая ошибка при запуске: {ex}", exc_info=True)
            attempt += 1
            if attempt < MAX_RETRIES:
                logger.info(f"Попытка {attempt + 1} через {RETRY_DELAY} секунд...")
                time.sleep(RETRY_DELAY)
    else:
        logger.critical("Бот не смог запуститься после 3 попыток. Выход.")


if __name__ == "__main__":
    main()
