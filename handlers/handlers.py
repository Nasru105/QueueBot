from telegram.ext import ContextTypes
from telegram import Update, InlineKeyboardMarkup

from services.queue_logger import QueueLogger
from services.queue_manager import queue_manager
from utils.InlineKeyboards import queue_keyboard, queues_keyboard
from utils.utils import safe_delete, get_user_name, update_existing_queues_info


async def handle_queue_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает нажатие кнопок внутри конкретной очереди (join/leave).
    """
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_name = get_user_name(user)
    chat = query.message.chat
    # message_thread_id = query.message.message_thread_id

    _, queue_index, action = query.data.split("|")
    queues = await queue_manager.get_queues(chat.id)
    queue_name = list(queues)[int(queue_index)]

    # Логика присоединения/выхода пользователя из очереди
    if action == "join" and user_name not in await queue_manager.get_queue(chat.id, queue_name):
        await queue_manager.add_to_queue(chat, queue_name, user_name)
    elif action == "leave" and user_name in await queue_manager.get_queue(chat.id, queue_name):
        await queue_manager.remove_from_queue(chat, queue_name, user_name)
    else:
        return  # Игнорируем, если действие не применимо

    # Удаляем старое сообщение очереди
    # last_id = await queue_manager.get_last_queue_message_id(chat.id, queue_name)
    # if last_id:
    #     await safe_delete(context, chat, last_id)

    # Получаем актуальный индекс очереди (если список изменился)
    queues = await queue_manager.get_queues(chat.id)
    queue_index = list(queues).index(queue_name)

    await query.edit_message_text(
        text=await queue_manager.get_queue_text(chat.id, queue_name),
        parse_mode="MarkdownV2",
        reply_markup=queue_keyboard(queue_index))

    # Отправляем обновлённое сообщение
    # sent = await context.bot.send_message(
    #     chat_id=chat.id,
    #     text=await queue_manager.get_queue_text(chat.id, queue_name),
    #     parse_mode="MarkdownV2",
    #     reply_markup=queue_keyboard(queue_index),
    #     message_thread_id=message_thread_id
    # )

    await queue_manager.set_last_queue_message_id(chat.id, queue_name, query.message.message_id)


async def handle_queues_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает нажатие кнопок списка всех очередей (get/delete).
    """
    query = update.callback_query
    user_id = query.from_user.id
    chat = query.message.chat
    await query.answer()

    _, queue_index, action = query.data.split("|")
    queues = await queue_manager.get_queues(chat.id)

    if action == "hide":
        # Удаляем старое меню очередей, если есть
        last_queues_id = await queue_manager.get_last_queues_message_id(chat.id)
        if last_queues_id:
            await safe_delete(context, chat, last_queues_id)
        return

    if queue_index != "all":
        queue_name = list(queues).pop(int(queue_index))

    # Показать очередь
    if action == "get":
        message_thread_id = query.message.message_thread_id

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
            message_thread_id=message_thread_id
        )

        await queue_manager.set_last_queue_message_id(chat.id, queue_name, sent.message_id)

    elif action == "delete" and queue_index == "all":

        member = await context.bot.get_chat_member(chat.id, user_id)
        if chat.title and member.status not in ('administrator', 'creator'):
            return
        # Удаляем старое меню очередей, если есть
        last_queues_id = await queue_manager.get_last_queues_message_id(chat.id)
        if last_queues_id:
            await safe_delete(context, chat, last_queues_id)

        queues = await queue_manager.get_queues(chat.id)
        for queue_name in list(queues.keys()):

            last_id = await queue_manager.get_last_queue_message_id(chat.id, queue_name)
            if last_id:
                await safe_delete(context, chat, last_id)

            await queue_manager.delete_queue(chat, queue_name)

    # Удалить очередь
    elif action == "delete":
        message = query.message

        member = await context.bot.get_chat_member(chat.id, user_id)
        if chat.title and member.status not in ('administrator', 'creator'):
            return

        last_id = await queue_manager.get_last_queue_message_id(chat.id, queue_name)
        if last_id:
            await safe_delete(context, chat, last_id)

        await queue_manager.delete_queue(message.chat, queue_name)

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
    chat = update.effective_chat
    QueueLogger.log(chat.title or chat.username, action=f"Exception: {context.error}")
