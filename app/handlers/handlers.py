# app/handlers/queue_handlers.py
import logging
from asyncio import Lock

from telegram import Chat, Update
from telegram.ext import ContextTypes

from ..queue_service import queue_service
from ..services.logger import QueueLogger
from ..utils.InlineKeyboards import queues_keyboard
from ..utils.utils import safe_delete

# Локи на чат
chat_locks: dict[int, Lock] = {}


def get_chat_lock(chat_id: int) -> Lock:
    if chat_id not in chat_locks:
        chat_locks[chat_id] = Lock()
    return chat_locks[chat_id]


async def is_user_admin(chat, user_id, context) -> bool:
    try:
        member = await context.bot.get_chat_member(chat.id, user_id)
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

    # Безопасное получение данных из callback
    try:
        _, queue_index_str, action = query.data.split("|")
        queue_index = int(queue_index_str)
    except ValueError:
        QueueLogger.log(chat_title, action="Invalid callback data", level=logging.WARNING)
        return

    queues = await queue_service.repo.get_all_queues(chat.id)
    if not (0 <= queue_index < len(queues)):
        QueueLogger.log(chat_title, action="Invalid queue index", level=logging.WARNING)
        return

    queue_name = list(queues.keys())[queue_index]

    async with get_chat_lock(chat.id):
        current_queue = await queue_service.repo.get_queue(chat.id, queue_name)
        if action == "join" and user_name not in current_queue:
            await queue_service.add_to_queue(chat.id, queue_name, user_name, chat_title)
        elif action == "leave" and user_name in current_queue:
            await queue_service.remove_from_queue(chat.id, queue_name, user_name, chat_title)
        else:
            return

    await queue_service.update_queue_message(
        chat_id=chat.id, queue_name=queue_name, query_or_update=query, context=context, chat_title=chat_title
    )


async def handle_queues_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает нажатие кнопок списка всех очередей (get/delete/hide).
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat = query.message.chat
    chat_title = chat.title or chat.username or "Личный чат"

    try:
        _, queue_index_str, action = query.data.split("|")
    except ValueError:
        QueueLogger.log(chat_title, action="Invalid callback data", level=logging.WARNING)
        return

    if action == "hide":
        last_queues_id = await queue_service.repo.get_list_message_id(chat.id)
        if last_queues_id:
            await safe_delete(context, chat, last_queues_id)
            await queue_service.repo.clear_list_message_id(chat.id)
        return

    queues = await queue_service.repo.get_all_queues(chat.id)

    if queue_index_str == "all":
        queue_name = None
    else:
        try:
            queue_index = int(queue_index_str)
            if not (0 <= queue_index < len(queues)):
                QueueLogger.log(chat_title, action="Invalid queue index", level=logging.WARNING)
                return
            queue_name = list(queues.keys())[queue_index]
        except ValueError:
            QueueLogger.log(chat_title, action="Invalid queue index format", level=logging.WARNING)
            return

    # Показать очередь
    if action == "get" and queue_name:
        await show_queue(query, context, chat, queue_name, chat_title)

    # Удалить все очереди
    elif action == "delete" and queue_index_str == "all":
        if chat.title and not await is_user_admin(chat, user_id, context):
            await query.answer("Только админы могут удалять все очереди!", show_alert=True)
            return
        async with get_chat_lock(chat.id):
            await delete_all_queues(chat, context, chat_title)

    # Удалить конкретную очередь
    elif action == "delete" and queue_name:
        if chat.title and not await is_user_admin(chat, user_id, context):
            await query.answer("Только админы могут удалять очереди!", show_alert=True)
            return
        async with get_chat_lock(chat.id):
            await delete_queue(chat, queue_name, query, context, chat_title)


async def show_queue(query, context: ContextTypes.DEFAULT_TYPE, chat: Chat, queue_name: str, chat_title: str):
    # Передаём chat и thread_id напрямую
    thread_id = query.message.message_thread_id if query.message else None

    await queue_service.send_queue_message(chat=chat, thread_id=thread_id, context=context, queue_name=queue_name)


async def delete_all_queues(chat, context: ContextTypes.DEFAULT_TYPE, chat_title: str):
    # Удаляем меню очередей
    last_id = await queue_service.repo.get_list_message_id(chat.id)
    if last_id:
        await safe_delete(context, chat, last_id)

    queues = await queue_service.repo.get_all_queues(chat.id)
    for queue_name in list(queues.keys()):
        last_id = await queue_service.repo.get_queue_message_id(chat.id, queue_name)
        if last_id:
            await safe_delete(context, chat, last_id)
        await queue_service.delete_queue(chat.id, queue_name, chat_title)


async def delete_queue(chat, queue_name: str, query, context: ContextTypes.DEFAULT_TYPE, chat_title: str):
    message = query.message

    # Удаляем сообщение очереди
    last_id = await queue_service.repo.get_queue_message_id(chat.id, queue_name)
    if last_id:
        await safe_delete(context, chat, last_id)

    await queue_service.delete_queue(chat.id, queue_name, chat_title)

    # Обновляем меню очередей
    queues = await queue_service.repo.get_all_queues(chat.id)
    await queue_service.update_existing_queues_info(context.bot, chat, queues)

    if queues:
        new_keyboard = await queues_keyboard(list(queues.keys()))
        await message.edit_reply_markup(reply_markup=new_keyboard)
    else:
        await safe_delete(context, chat, message.message_id)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Глобальный обработчик ошибок.
    """
    chat_title = update.effective_chat.title if update and update.effective_chat else "Unknown Chat"

    QueueLogger.log(
        chat_title=chat_title,
        action=f"Exception: {context.error}",
        level=logging.ERROR,
    )
