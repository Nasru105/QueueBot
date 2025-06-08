from telegram.ext import CommandHandler, CallbackQueryHandler

from handlers.handlers import handle_button, error_handler
from utils.utils import start_help
from .admin import clear_queue, insert_user, remove_user, generate_queue, get_list_of_students
from .queue import join, leave, queue


def register_handlers(app):
    app.add_handler(CommandHandler("start", start_help))
    app.add_handler(CommandHandler("help", start_help))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("leave", leave))
    app.add_handler(CommandHandler("queue", queue))

    app.add_handler(CommandHandler("clear", clear_queue))
    app.add_handler(CommandHandler("insert", insert_user))
    app.add_handler(CommandHandler("remove", remove_user))

    app.add_handler(CommandHandler("generatequeue", generate_queue))
    app.add_handler(CommandHandler("getlist", get_list_of_students))

    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_error_handler(error_handler)


async def set_commands(app):
    await app.bot.set_my_commands([
        ("join", "Встать в очередь"),
        ("leave", "Покинуть очередь"),
        ("queue", "Показать очередь"),
    ])
