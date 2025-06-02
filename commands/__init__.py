from telegram.ext import CommandHandler, CallbackQueryHandler

from handlers.handlers import handle_button, error_handler
from .admin import clear_queue, insert_user, remove_user, generate_queue, generate_a_queue, generate_b_queue
from .queue import join, leave, queue


def register_handlers(app):
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("leave", leave))
    app.add_handler(CommandHandler("queue", queue))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(CommandHandler("clear", clear_queue))
    app.add_handler(CommandHandler("insertuser", insert_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("generatequeue", generate_queue))
    app.add_handler(CommandHandler("generateaqueue", generate_a_queue))
    app.add_handler(CommandHandler("generatebqueue", generate_b_queue))
    app.add_error_handler(error_handler)

async def set_commands(app):
    await app.bot.set_my_commands([
        ("join", "Встать в очередь"),
        ("leave", "Покинуть очередь"),
        ("queue", "Показать очередь"),
    ])
