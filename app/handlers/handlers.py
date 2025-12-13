# app/handlers/queue_handlers.py
import logging

# import traceback
from asyncio import Lock

from telegram import Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.queues_menu.queue_menu import handle_queue_menu
from app.queues_menu.queues_menu import handle_queues_menu
from app.services.logger import QueueLogger
from app.utils.utils import with_ctx

# Локи на чат
chat_locks: dict[int, Lock] = {}


def get_chat_lock(chat_id: int) -> Lock:
    if chat_id not in chat_locks:
        chat_locks[chat_id] = Lock()
    return chat_locks[chat_id]


@with_ctx
async def handle_queue_button(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    """
    Обрабатывает нажатие кнопок внутри конкретной очереди (join/leave).
    """
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_name = await queue_service.get_user_display_name(user, ctx.chat_id)

    # Безопасное получение данных из callback
    try:
        _, queue_index_str, action = query.data.split("|")
        queue_index = int(queue_index_str)
    except ValueError:
        QueueLogger.log(ctx, action="Invalid callback data", level=logging.WARNING)
        return

    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    if not (0 <= queue_index < len(queues)):
        QueueLogger.log(ctx, action="Invalid queue index", level=logging.WARNING)
        return

    queue_name = list(queues.keys())[queue_index]
    ctx.queue_name = queue_name

    async with get_chat_lock(ctx.chat_id):
        current_queue = await queue_service.repo.get_queue(ctx.chat_id, queue_name)
        if action == "join" and user_name not in current_queue:
            await queue_service.join_to_queue(ctx, user_name)
        elif action == "leave" and user_name in current_queue:
            await queue_service.leave_from_queue(ctx, user_name)
        else:
            return

    await queue_service.update_queue_message(ctx, query_or_update=query, context=context)


@with_ctx
async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    query = update.callback_query
    await query.answer()

    try:
        _, menu_type, queue_index, action = query.data.split("|")
    except ValueError:
        QueueLogger.log(ctx, "Invalid menu callback", level=logging.WARNING)
        return

    if menu_type == "queue":
        await handle_queue_menu(update, context, ctx, int(queue_index), action)
    elif menu_type == "queues":
        await handle_queues_menu(update, context, ctx, queue_index, action)


@with_ctx
async def menu_queue_router(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    query = update.callback_query
    await query.answer()

    try:
        _, menu_type, queue_index, action = query.data.split("|")
    except ValueError:
        QueueLogger.log(ctx, "Invalid menu callback", level=logging.WARNING)
        return

    if menu_type == "swap":
        ...


# async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
#     """
#     Глобальный обработчик ошибок.
#     """
#     chat_title = update.effective_ctx.chat_title if update and update.effective_chat else "Unknown Chat"

#     error_trace = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
#     QueueLogger.log(
#         chat_title=chat_title,
#         action=f"Exception: {error_trace}",
#         level=logging.ERROR,
#     )
