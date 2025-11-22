from telegram.ext import CallbackQueryHandler, CommandHandler

from app.handlers.handlers import error_handler, handle_queue_button, handle_queues_button

from .admin import (
    admin_help,
    delete_all_queues,
    delete_queue,
    insert_user,
    remove_user,
    rename_queue,
    replace_users,
)
from .queue import create, nickname, nickname_global, queues, start_help


def register_handlers(app):
    app.add_handler(CommandHandler("start", start_help))
    app.add_handler(CommandHandler("help", start_help))

    app.add_handler(CommandHandler("create", create))
    app.add_handler(CommandHandler("queues", queues))
    app.add_handler(CommandHandler("nickname", nickname))
    app.add_handler(CommandHandler("nickname_global", nickname_global))

    app.add_handler(CommandHandler("delete", delete_queue))
    app.add_handler(CommandHandler("delete_all", delete_all_queues))
    app.add_handler(CommandHandler("insert", insert_user))
    app.add_handler(CommandHandler("remove", remove_user))
    app.add_handler(CommandHandler("replace", replace_users))
    app.add_handler(CommandHandler("rename", rename_queue))

    # app.add_handler(CommandHandler("admin_help", admin_help))
    # app.add_handler(CommandHandler("generate", generate_queue))
    # app.add_handler(CommandHandler("getlist", get_list_of_students))

    app.add_handler(CallbackQueryHandler(handle_queue_button, pattern=r"^queue\|"))
    app.add_handler(CallbackQueryHandler(handle_queues_button, pattern=r"^queues\|"))
    app.add_error_handler(error_handler)


async def set_commands(app):
    await app.bot.set_my_commands(
        [
            ("create", "Создать очередь"),
            ("queues", "Показать список очередей"),
        ]
    )
