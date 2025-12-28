from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from app.commands.admin import (
    delete_all_queues,
    delete_queue,
    insert_user,
    remove_user,
    rename_queue,
    replace_users,
    set_queue_expiration_time,
)
from app.commands.help import commands_list, help_command, start
from app.commands.queue import chat_nickname, create, global_nickname, queues
from app.commands.reports import get_jobs, get_logs
from app.queues.router import queue_router
from app.queues_menu.router import menu_router


def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("commands", commands_list))

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

    app.add_handler(CommandHandler("set_expire_time", set_queue_expiration_time))

    app.add_handler(CommandHandler("logs", get_logs))
    app.add_handler(CommandHandler("jobs", get_jobs))

    app.add_handler(CallbackQueryHandler(queue_router, pattern=r"^queue\|"))
    app.add_handler(CallbackQueryHandler(menu_router, pattern=r"^menu\|"))
    # app.add_error_handler(error_handler)


async def set_commands(app: Application):
    await app.bot.set_my_commands(
        [
            ("create", "/create [Имя очереди] — создаёт очередь"),
            ("queues", "Показать список очередей"),
        ]
    )
