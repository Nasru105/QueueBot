import os

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder

from commands import register_handlers, set_commands

try:
    load_dotenv()  # Загружает переменные из .env
    TOKEN = os.getenv("TOKEN")
    app = ApplicationBuilder().token(TOKEN).post_init(set_commands).build()
    register_handlers(app)
    app.run_polling()
except Exception as ex:
    print(f"Error: {ex}")