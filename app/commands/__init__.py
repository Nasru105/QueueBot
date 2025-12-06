from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from app.handlers.handlers import handle_queue_button, handle_queues_button

from .admin import delete_all_queues, delete_queue, get_logs, insert_user, remove_user, rename_queue, replace_users
from .queue import chat_nickname, create, global_nickname, queues, start_help


def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", start_help))
    app.add_handler(CommandHandler("help", start_help))

    app.add_handler(CommandHandler("create", create))
    app.add_handler(CommandHandler("queues", queues))
    app.add_handler(CommandHandler("nickname", chat_nickname))
    app.add_handler(CommandHandler("nickname_global", global_nickname))

    app.add_handler(CommandHandler("delete", delete_queue))
    app.add_handler(CommandHandler("delete_all", delete_all_queues))
    app.add_handler(CommandHandler("insert", insert_user))
    app.add_handler(CommandHandler("remove", remove_user))
    app.add_handler(CommandHandler("replace", replace_users))
    app.add_handler(CommandHandler("rename", rename_queue))

    app.add_handler(CommandHandler("logs", get_logs))

    app.add_handler(CallbackQueryHandler(handle_queue_button, pattern=r"^queue\|"))
    app.add_handler(CallbackQueryHandler(handle_queues_button, pattern=r"^queues\|"))
    # app.add_error_handler(error_handler)


async def set_commands(app: Application):
    await app.bot.set_my_commands(
        [
            ("create", "/create [Имя очереди] — создаёт очередь"),
            ("queues", "Показать список очередей"),
        ]
    )
