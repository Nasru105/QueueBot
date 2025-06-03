from telegram.ext import ContextTypes, CallbackQueryHandler

from services.queue_service import (
    add_to_queue, remove_from_queue, get_queue, get_last_message_id,
    set_last_message_id, get_queue_message, sent_queue_message
)

from utils.utils import safe_delete, get_queue_keyboard

from telegram import Update


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    message_id = update.message.message_id
    await safe_delete(context, chat_id, message_id)
    name = f"{user.first_name} {user.last_name or ''}".strip()
    if name in get_queue(chat_id):
        return
    add_to_queue(chat_id, name)

    await sent_queue_message(update, context)


async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    user = update.effective_user

    await safe_delete(context, chat_id, message_id)

    name = f"{user.first_name} {user.last_name or ''}".strip()
    if name not in get_queue(chat_id):
        return

    remove_from_queue(chat_id, name)

    await sent_queue_message(update, context)


async def queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message_id = update.message.message_id

    await safe_delete(context, chat_id, message_id)

    await sent_queue_message(update, context)
