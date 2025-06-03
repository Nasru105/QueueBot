from telegram.ext import ContextTypes
from telegram import Update

from services.queue_service import (
    add_to_queue, remove_from_queue,
    get_queue_text, set_last_message_id,
    get_last_message_id, get_queue
)
from utils.utils import get_queue_keyboard, safe_delete, get_name


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    name = get_name(user)
    chat_id = query.message.chat_id
    message_thread_id = query.message.message_thread_id
    data = query.data

    if data == "join" and name not in get_queue(chat_id):
        add_to_queue(chat_id, name)
    elif data == "leave" and name in get_queue(chat_id):
        remove_from_queue(chat_id, name)
    else:
        return

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=get_queue_text(chat_id),
        reply_markup=get_queue_keyboard(),
        message_thread_id=message_thread_id
    )

    last_id = get_last_message_id(chat_id)
    if last_id:
        await safe_delete(context, chat_id, last_id)

    set_last_message_id(chat_id, sent.message_id)

async def error_handler(update, context):
    print(f"Exception: {context.error}")