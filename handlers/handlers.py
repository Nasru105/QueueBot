from telegram.ext import ContextTypes
from telegram import Update, InlineKeyboardMarkup

from services.queue_service import queue_manager
from utils.InlineKeyboards import queue_keyboard, queues_keyboard
# from services.queue_service import (
#     add_to_queue, remove_from_queue,
#     get_queue_text, set_last_message_id,
#     get_last_message_id, get_queue
# )
from utils.utils import safe_delete, get_name, get_time


async def handle_queue_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_name = get_name(user)
    chat = query.message.chat
    message_thread_id = query.message.message_thread_id

    _, queue_index, action = query.data.split("|")
    queues = await queue_manager.get_queues(chat.id)
    queue_name = list(queues)[int(queue_index)]

    if action == "join" and user_name not in await queue_manager.get_queue(chat.id, queue_name):
        await queue_manager.add_to_queue(chat, queue_name, user_name)
    elif action == "leave" and user_name in await queue_manager.get_queue(chat.id, queue_name):
        await queue_manager.remove_from_queue(chat, queue_name, user_name)
    else:
        return

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


async def handle_queues_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat = query.message.chat
    await query.answer()

    _, queue_index, action = query.data.split("|")

    queues = await queue_manager.get_queues(chat.id)
    queue_name = list(queues).pop(int(queue_index))

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

    elif action == "delete":
        message = query.message

        # Чистим последнее сообщение очереди
        last_id = await queue_manager.get_last_queue_message_id(chat.id, queue_name)
        if last_id:
            await safe_delete(context, chat, last_id)

        await queue_manager.delete_queue(message.chat, queue_name)

        if list(queues):
            new_keyboard = await queues_keyboard(list(queues))
            await message.edit_reply_markup(reply_markup=new_keyboard)
        else:
            await safe_delete(context, chat, message.message_id)


async def error_handler(update, context):
    chat = update.effective_chat

    print(f"{chat.title if chat.title else chat.username}: {get_time()} Exception: {context.error}", flush=True)
