import os
import time

from commands import register_handlers, set_commands
from dotenv import load_dotenv
from services.logger import logger
from telegram.ext import ApplicationBuilder

load_dotenv()
TOKEN = os.getenv("TOKEN")

MAX_RETRIES = 3
RETRY_DELAY = 15  # секунд между попытками


def main():
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
