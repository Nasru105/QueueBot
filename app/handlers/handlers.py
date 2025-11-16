import logging
import traceback
from asyncio import Lock

from telegram import Update
from telegram.ext import ContextTypes

from app.services.storage import load_users_names, save_users_names

from ..services.logger import QueueLogger
from ..services.queue_manager import queue_manager
from ..utils.InlineKeyboards import queue_keyboard, queues_keyboard
from ..utils.utils import get_user_name, safe_delete, update_existing_queues_info

# Локи на чат
chat_locks: dict[int, Lock] = {}


def get_chat_lock(chat_id: int) -> Lock:
    if chat_id not in chat_locks:
        chat_locks[chat_id] = Lock()
    return chat_locks[chat_id]


# Кеш пользователей
users_names_cache = load_users_names()


async def is_user_admin(chat, user_id, context) -> bool:
    member = await context.bot.get_chat_member(chat.id, user_id)
    return member.status in ("administrator", "creator")


async def handle_queue_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает нажатие кнопок внутри конкретной очереди (join/leave).
    """
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_name = get_user_name(user)
    chat = query.message.chat

    # Безопасное получение данных из callback
    try:
        _, queue_index, action = query.data.split("|")
        queue_index = int(queue_index)
    except ValueError:
        QueueLogger.log(chat.title or chat.username, action="Invalid callback data", level=logging.WARNING)
        return

    queues = await queue_manager.get_queues(chat.id)
    if not (0 <= queue_index < len(queues)):
        QueueLogger.log(chat.title or chat.username, action="Invalid queue index", level=logging.WARNING)
        return
    queue_name = list(queues)[queue_index]

    # Добавляем пользователя в кеш, если нужно
    if str(user.id) not in users_names_cache:
        users_names_cache[str(user.id)] = user_name
        save_users_names(users_names_cache)

    async with get_chat_lock(chat.id):
        current_queue = await queue_manager.get_queue(chat.id, queue_name)
        if action == "join" and user_name not in current_queue:
            await queue_manager.add_to_queue(chat, queue_name, user_name)
        elif action == "leave" and user_name in current_queue:
            await queue_manager.remove_from_queue(chat, queue_name, user_name)
        else:
            return  # действие не применимо

    await queue_manager.update_queue_message(chat, query, queue_name, context)


async def handle_queues_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает нажатие кнопок списка всех очередей (get/delete/hide).
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat = query.message.chat

    try:
        _, queue_index, action = query.data.split("|")
    except ValueError:
        QueueLogger.log(chat.title or chat.username, action="Invalid callback data", level=logging.WARNING)
        return

    queues = await queue_manager.get_queues(chat.id)

    if action == "hide":
        # Удаляем старое меню очередей
        last_queues_id = await queue_manager.get_last_queues_message_id(chat.id)
        if last_queues_id:
            await safe_delete(context, chat, last_queues_id)
            await queue_manager.delete_last_queues_message_id(chat.id, last_queues_id)
        return

    if queue_index != "all":
        try:
            queue_index = int(queue_index)
            if not (0 <= queue_index < len(queues)):
                QueueLogger.log(
                    chat.title or chat.username, action="Invalid queue index in queues menu", level=logging.WARNING
                )
                return
            queue_name = list(queues)[queue_index]
        except ValueError:
            QueueLogger.log(
                chat.title or chat.username, action="Invalid queue index format in queues menu", level=logging.WARNING
            )
            return

    # Показать очередь
    if action == "get":
        await show_queue(chat, queue_name, query, context)
    # Удалить все очереди
    elif action == "delete" and queue_index == "all":
        if chat.title and not await is_user_admin(chat, user_id, context):
            return
        async with get_chat_lock(chat.id):
            await delete_all_queues(chat, context)
    # Удалить конкретную очередь
    elif action == "delete":
        if chat.title and not await is_user_admin(chat, user_id, context):
            return
        async with get_chat_lock(chat.id):
            await delete_queue(chat, queue_name, query, context)


async def show_queue(chat, queue_name, query, context):
    message_thread_id = query.message.message_thread_id

    # Удаляем старое сообщение очереди
    last_id = await queue_manager.get_last_queue_message_id(chat.id, queue_name)
    if last_id:
        await safe_delete(context, chat, last_id)

    queues = await queue_manager.get_queues(chat.id)
    queue_index = list(queues).index(queue_name)

    sent = await context.bot.send_message(
        chat_id=chat.id,
        text=await queue_manager.get_queue_text(chat.id, queue_name),
        parse_mode="MarkdownV2",
        reply_markup=queue_keyboard(queue_index),
        message_thread_id=message_thread_id,
    )
    await queue_manager.set_last_queue_message_id(chat.id, queue_name, sent.message_id)


async def delete_all_queues(chat, context):
    # Удаляем старое меню очередей
    last_queues_id = await queue_manager.get_last_queues_message_id(chat.id)
    if last_queues_id:
        await safe_delete(context, chat, last_queues_id)

    queues = await queue_manager.get_queues(chat.id)
    for queue_name in list(queues.keys()):
        last_id = await queue_manager.get_last_queue_message_id(chat.id, queue_name)
        if last_id:
            await safe_delete(context, chat, last_id)
        await queue_manager.delete_queue(chat, queue_name)


async def delete_queue(chat, queue_name, query, context):
    message = query.message

    # Удаляем старое сообщение очереди
    last_id = await queue_manager.get_last_queue_message_id(chat.id, queue_name)
    if last_id:
        await safe_delete(context, chat, last_id)

    await queue_manager.delete_queue(chat, queue_name)

    # Обновляем меню очередей
    queues = await queue_manager.get_queues(chat.id)
    await update_existing_queues_info(context.bot, queue_manager, chat, queues)

    if list(queues):
        new_keyboard = await queues_keyboard(list(queues))
        await message.edit_reply_markup(reply_markup=new_keyboard)
    else:
        await safe_delete(context, chat, message.message_id)


async def error_handler(update, context):
    """
    Глобальный обработчик ошибок.
    Логирует все необработанные исключения, возникающие во время работы бота.
    """
    if update and update.effective_chat:
        chat_title = update.effective_chat.title or update.effective_chat.username
    else:
        chat_title = "Unknown Chat"

    error_trace = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
    QueueLogger.log(
        chat_title=chat_title,
        action=f"Exception: {error_trace}",
        level=logging.ERROR,
    )
