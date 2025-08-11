from telegram.ext import ContextTypes
from telegram import Update, InlineKeyboardMarkup

from services.queue_service import queue_manager
from utils.InlineKeyboards import queue_keyboard
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
    _, queue_name, action = query.data.split("|")

    if action == "join" and user_name not in await queue_manager.get_queue(chat.id, queue_name):
        await queue_manager.add_to_queue(chat, queue_name, user_name)
    elif action == "leave" and user_name in await queue_manager.get_queue(chat.id, queue_name):
        await queue_manager.remove_from_queue(chat, queue_name, user_name)
    else:
        return

    await queue_manager.send_queue_message(update, context, queue_name)


async def handle_queues_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat = query.message.chat
    await query.answer()

    _, queue_name, action = query.data.split("|")
    if action == "get":
        await queue_manager.send_queue_message(update, context, queue_name)

    elif action == "delete":
        # Получаем текущее сообщение и клавиатуру
        message = query.message
        markup = message.reply_markup.inline_keyboard

        # Удаляем из клавиатуры кнопки, которые относятся к этой очереди
        new_keyboard = [
            row for row in markup
            if not any(btn.callback_data and queue_name in btn.callback_data for btn in row)
        ]
        if not new_keyboard:
            await safe_delete(context, chat, message.message_id)
        else:
            # Обновляем сообщение с новой клавиатурой
            await message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))

        last_id = await queue_manager.get_last_queue_message_id(chat.id, queue_name)
        if last_id:
            await safe_delete(context, chat, last_id)

        # удаляем саму очередь из данных
        await queue_manager.delete_queue(message.chat, queue_name)


async def error_handler(update, context):
    chat = update.effective_chat

    print(f"{chat.title if chat.title else chat.username}: {get_time()} Exception: {context.error}", flush=True)
