# app/handlers/queue_handlers.py
import logging

# import traceback
from asyncio import Lock, create_task

from telegram import Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.services.logger import QueueLogger
from app.utils.utils import delete_later, is_user_admin, safe_delete, with_ctx

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
async def handle_queues_button(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    """
    Обрабатывает нажатие кнопок списка всех очередей (get/delete/hide).
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat = query.message.chat

    try:
        _, queue_index_str, action = query.data.split("|")
    except ValueError:
        QueueLogger.log(ctx, action="Invalid callback data", level=logging.WARNING)
        return

    if action == "hide":
        last_queues_id = await queue_service.repo.get_list_message_id(ctx.chat_id)
        if last_queues_id:
            await safe_delete(context.bot, ctx, last_queues_id)
            await queue_service.repo.clear_list_message_id(ctx.chat_id)
        return

    queues = await queue_service.repo.get_all_queues(ctx.chat_id)

    if queue_index_str == "all":
        queue_name = None
    else:
        try:
            queue_index = int(queue_index_str)
            if not (0 <= queue_index < len(queues)):
                QueueLogger.log(ctx, action="Invalid queue index", level=logging.WARNING)
                return
            queue_name = list(queues.keys())[queue_index]
        except ValueError:
            QueueLogger.log(ctx, action="Invalid queue index format", level=logging.WARNING)
            return
    ctx.queue_name = queue_name

    # Показать очередь
    if action == "get" and queue_name:
        await show_queue(ctx, context)

    # Удалить все очереди
    elif action == "delete" and queue_index_str == "all":
        if chat.title and not await is_user_admin(context, ctx.chat_id, user_id):
            error_message = await context.bot.send_message(
                ctx.chat_id, "Вы не являетесь администратором", message_thread_id=ctx.thread_id
            )
            create_task(delete_later(context, ctx, error_message.message_id))
            return
        async with get_chat_lock(ctx.chat_id):
            await delete_all_queues(ctx, context)

    # Удалить конкретную очередь
    elif action == "delete" and queue_name:
        if chat.title and not await is_user_admin(context, ctx.chat_id, user_id):
            error_message = await context.bot.send_message(
                ctx.chat_id, "Вы не являетесь администратором", message_thread_id=ctx.thread_id
            )
            create_task(delete_later(context, ctx, error_message.message_id))
            return
        async with get_chat_lock(ctx.chat_id):
            await delete_queue(ctx, query, context)


async def show_queue(ctx, context: ContextTypes.DEFAULT_TYPE):
    await queue_service.send_queue_message(ctx, context)


async def delete_all_queues(ctx: ActionContext, context: ContextTypes.DEFAULT_TYPE):
    # Удаляем меню очередей
    last_id = await queue_service.repo.get_list_message_id(ctx.chat_id)
    if last_id:
        await safe_delete(context.bot, ctx, last_id)

    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    for queue_name in list(queues.keys()):
        ctx.queue_name = queue_name

        last_id = await queue_service.repo.get_queue_message_id(ctx.chat_id, queue_name)
        if last_id:
            await safe_delete(context.bot, ctx, last_id)
        await queue_service.delete_queue(ctx)


async def delete_queue(ctx: ActionContext, query, context: ContextTypes.DEFAULT_TYPE):
    message = query.message

    # Удаляем сообщение очереди
    last_id = await queue_service.repo.get_queue_message_id(ctx.chat_id, ctx.queue_name)
    if last_id:
        await safe_delete(context.bot, ctx, last_id)

    await queue_service.delete_queue(ctx)

    # Обновляем меню очередей
    await queue_service.mass_update_existing_queues(context.bot, ctx, message.message_id)


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
