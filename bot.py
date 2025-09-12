import os
import time
import asyncio
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder
from commands import register_handlers, set_commands

load_dotenv()  # Загружает переменные из .env
TOKEN = os.getenv("TOKEN")

while True:
    try:
        # создаём новый event loop при каждой итерации
        asyncio.set_event_loop(asyncio.new_event_loop())

        app = (
            ApplicationBuilder()
            .token(TOKEN)
            .read_timeout(30)
            .write_timeout(30)
            .post_init(set_commands)
            .build()
        )
        register_handlers(app)

        print("Бот запущен. Ожидание сообщений...")
        app.run_polling()
    except Exception as ex:
        print(f"Ошибка: {ex}")
        print("Перезапуск через 5 секунд...")
        time.sleep(5)
