from telegram.ext import CommandHandler, CallbackQueryHandler

from commands.admin import delete_queue, delete_queues, insert_user, remove_user, replace_users, generate_queue
from commands.queue import create, queues
from handlers.handlers import handle_queue_button, error_handler, handle_queues_button
from utils.utils import start_help


def register_handlers(app):
    app.add_handler(CommandHandler("start", start_help))
    app.add_handler(CommandHandler("help", start_help))

    app.add_handler(CommandHandler("create", create))
    app.add_handler(CommandHandler("queues", queues))

    app.add_handler(CommandHandler("delete", delete_queue))
    app.add_handler(CommandHandler("delete_all", delete_queues))
    app.add_handler(CommandHandler("insert", insert_user))
    app.add_handler(CommandHandler("remove", remove_user))
    app.add_handler(CommandHandler("replace", replace_users))
    #
    app.add_handler(CommandHandler("generatequeue", generate_queue))
    # app.add_handler(CommandHandler("getlist", get_list_of_students))
    #
    app.add_handler(CallbackQueryHandler(handle_queue_button, pattern=r"^queue\|"))
    app.add_handler(CallbackQueryHandler(handle_queues_button, pattern=r"^queues\|"))
    # app.add_error_handler(error_handler)


async def set_commands(app):
    await app.bot.set_my_commands([
        ("create", "Создать очередь"),
        ("queues", "Показать список очередей"),
    ])
