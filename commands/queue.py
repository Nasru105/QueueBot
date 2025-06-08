from telegram.ext import ContextTypes
from services.queue_service import (
    add_to_queue, remove_from_queue, get_queue, sent_queue_message
)
from utils.utils import safe_delete, get_name
from telegram import Update


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message_id = update.message.message_id
    await safe_delete(context, chat, message_id)
    name = get_name(user)
    if name in get_queue(chat.id):
        return
    add_to_queue(chat, name)

    await sent_queue_message(update, context)


async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message_id = update.message.message_id
    user = update.effective_user

    await safe_delete(context, chat, message_id)

    name = get_name(user)
    if name not in get_queue(chat.id):
        return

    remove_from_queue(chat, name)

    await sent_queue_message(update, context)


async def queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message_id = update.message.message_id

    await safe_delete(context, chat, message_id)

    await sent_queue_message(update, context)
