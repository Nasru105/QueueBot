# app/handlers/queue_handlers.py
import logging

# import traceback
from asyncio import Lock

from telegram import Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.services.logger import QueueLogger
from app.utils.InlineKeyboards import queues_keyboard
from app.utils.utils import safe_delete

# Локи на чат
chat_locks: dict[int, Lock] = {}


def get_chat_lock(chat_id: int) -> Lock:
    if chat_id not in chat_locks:
        chat_locks[chat_id] = Lock()
    return chat_locks[chat_id]


async def is_user_admin(chat_id, user_id, context) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def handle_queue_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает нажатие кнопок внутри конкретной очереди (join/leave).
    """
    query = update.callback_query
    await query.answer()

    user = query.from_user
    chat = query.message.chat
    chat_title = chat.title or chat.username or "Личный чат"
    user_name = await queue_service.get_user_display_name(user, chat.id)
    actor = user.username or "Unknown"
    thread_id = query.message.message_thread_id if query.message else None
    ctx = ActionContext(chat.id, chat_title, "", actor, thread_id)

    # Безопасное получение данных из callback
    try:
        _, queue_index_str, action = query.data.split("|")
        queue_index = int(queue_index_str)
    except ValueError:
        QueueLogger.log(ctx, action="Invalid callback data", level=logging.WARNING)
        return

    queues = await queue_service.repo.get_all_queues(chat.id)
    if not (0 <= queue_index < len(queues)):
        QueueLogger.log(ctx, action="Invalid queue index", level=logging.WARNING)
        return

    queue_name = list(queues.keys())[queue_index]
    ctx.queue_name = queue_name

    async with get_chat_lock(chat.id):
        current_queue = await queue_service.repo.get_queue(chat.id, queue_name)
        if action == "join" and user_name not in current_queue:
            await queue_service.join_to_queue(ctx, user_name)
        elif action == "leave" and user_name in current_queue:
            await queue_service.leave_from_queue(ctx, user_name)
        else:
            return

    await queue_service.update_queue_message(ctx, query_or_update=query, context=context)


async def handle_queues_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает нажатие кнопок списка всех очередей (get/delete/hide).
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat = query.message.chat
    chat_title = chat.title or chat.username or "Личный чат"
    actor = query.from_user.username or "Unknown"
    thread_id = query.message.message_thread_id if query.message else None

    ctx = ActionContext(chat.id, chat_title, "", actor, thread_id)

    try:
        _, queue_index_str, action = query.data.split("|")
    except ValueError:
        QueueLogger.log(ctx, action="Invalid callback data", level=logging.WARNING)
        return

    if action == "hide":
        last_queues_id = await queue_service.repo.get_list_message_id(chat.id)
        if last_queues_id:
            await safe_delete(context, ctx, last_queues_id)
            await queue_service.repo.clear_list_message_id(chat.id)
        return

    queues = await queue_service.repo.get_all_queues(chat.id)

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
        if chat.title and not await is_user_admin(chat.id, user_id, context):
            await query.answer("Только админы могут удалять все очереди!", show_alert=True)
            return
        async with get_chat_lock(chat.id):
            await delete_all_queues(ctx, context)

    # Удалить конкретную очередь
    elif action == "delete" and queue_name:
        if chat.title and not await is_user_admin(chat, user_id, context):
            await query.answer("Только админы могут удалять очереди!", show_alert=True)
            return
        async with get_chat_lock(chat.id):
            await delete_queue(ctx, query, context)


async def show_queue(ctx, context: ContextTypes.DEFAULT_TYPE):
    await queue_service.send_queue_message(ctx, context)


async def delete_all_queues(ctx: ActionContext, context: ContextTypes.DEFAULT_TYPE):
    # Удаляем меню очередей
    last_id = await queue_service.repo.get_list_message_id(ctx.chat_id)
    if last_id:
        await safe_delete(context, ctx, last_id)

    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    for queue_name in list(queues.keys()):
        ctx.queue_name = queue_name

        last_id = await queue_service.repo.get_queue_message_id(ctx.chat_id, queue_name)
        if last_id:
            await safe_delete(context, ctx, last_id)
        await queue_service.delete_queue(ctx)


async def delete_queue(ctx: ActionContext, query, context: ContextTypes.DEFAULT_TYPE):
    message = query.message

    # Удаляем сообщение очереди
    last_id = await queue_service.repo.get_queue_message_id(ctx.chat_id, ctx.queue_name)
    if last_id:
        await safe_delete(context, ctx, last_id)

    await queue_service.delete_queue(ctx)

    # Обновляем меню очередей
    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    await queue_service.mass_update_existing_queues(context.bot, ctx)

    if queues:
        new_keyboard = await queues_keyboard(list(queues.keys()))
        await message.edit_reply_markup(reply_markup=new_keyboard)
    else:
        await safe_delete(context, ctx, message.message_id)


# async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """
#     Глобальный обработчик ошибок.
#     """
#     chat_title = update.effective_chat.title if update and update.effective_chat else "Unknown Chat"

#     error_trace = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
#     QueueLogger.log(
#         chat_title=chat_title,
#         action=f"Exception: {error_trace}",
#         level=logging.ERROR,
#     )
