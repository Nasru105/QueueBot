from asyncio import create_task

from telegram.ext import ContextTypes

from utils.InlineKeyboards import queues_keyboard
# from services.queue_service import (
#     add_to_queue, remove_from_queue, get_queue, sent_queue_message
# )
from utils.utils import safe_delete, get_name, delete_later
from telegram import Update
from services.queue_service import queue_manager


async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message_id = update.message.message_id

    await safe_delete(context, chat, message_id)

    queue_name = " ".join(context.args)
    if not queue_name:
        count_queue = 0
        queue_name = f"Очередь {count_queue + 1}"
        while await queue_manager.get_queue(chat.id, queue_name):
            count_queue += 1
            queue_name = f"Очередь {count_queue }"

    await queue_manager.create_queue(chat, queue_name)

    await queue_manager.send_queue_message(update, context, queue_name)


async def queues(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message_id = update.message.message_id
    message_thread_id = update.message.message_thread_id if update.message else None

    await safe_delete(context, chat, message_id)

    queues_list = await queue_manager.get_queues(chat.id)

    # Удаляем старое меню очередей, если есть
    last_queues_id = await queue_manager.get_last_queues_message_id(chat.id)
    if last_queues_id:
        await safe_delete(context, chat, last_queues_id)

    if queues_list:
        sent = await context.bot.send_message(
            chat_id=chat.id,
            text="Выберите очередь:",
            reply_markup=await queues_keyboard(list(queues_list)),
            message_thread_id=message_thread_id
        )
        # Сохраняем новый message_id меню
        await queue_manager.set_last_queues_message_id(chat.id, sent.message_id)
    else:
        sent = await context.bot.send_message(
            chat_id=chat.id,
            text="Нет активных очередей",
            message_thread_id=message_thread_id
        )
        await queue_manager.set_last_queues_message_id(chat.id, None)
        create_task(delete_later(context, chat, sent.message_id, 10))

