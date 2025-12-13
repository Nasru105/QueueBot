import logging
from asyncio import create_task

# import traceback
from telegram import Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.queues_menu.inline_keyboards import queue_menu_keyboard
from app.services.logger import QueueLogger
from app.utils.utils import delete_later, is_user_admin, safe_delete


async def handle_queues_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext, queue_index: str, action: str
):
    """
    Обрабатывает нажатие кнопок списка всех очередей (get/delete/hide).
    """
    query = update.callback_query

    user_id = query.from_user.id
    chat = query.message.chat

    if action == "hide":
        last_queues_id = await queue_service.repo.get_list_message_id(ctx.chat_id)
        if last_queues_id:
            await safe_delete(context.bot, ctx, last_queues_id)
            await queue_service.repo.clear_list_message_id(ctx.chat_id)
        return

    # Показать очередь
    if action == "get":
        queues = await queue_service.repo.get_all_queues(ctx.chat_id)
        try:
            queue_index = int(queue_index)
            if not (0 <= queue_index < len(queues)):
                QueueLogger.log(ctx, action="Invalid queue index", level=logging.WARNING)
                return
            queue_name = list(queues.keys())[queue_index]
            ctx.queue_name = queue_name
        except ValueError as ex:
            QueueLogger.log(ctx, f"Invalid queue index {ex}", level=logging.ERROR)

        await query.edit_message_text(
            text=f"Действия с {queue_name}",
            parse_mode="MarkdownV2",
            reply_markup=await queue_menu_keyboard(queue_index),
        )

    # Удалить все очереди
    elif action == "delete":
        if chat.title and not await is_user_admin(context, ctx.chat_id, user_id):
            error_message = await context.bot.send_message(
                ctx.chat_id, "Вы не являетесь администратором", message_thread_id=ctx.thread_id
            )
            create_task(delete_later(context, ctx, error_message.message_id))
            return
        await delete_all_queues(ctx, context)


async def delete_all_queues(ctx: ActionContext, context: ContextTypes.DEFAULT_TYPE):
    # Удаляем меню очередей
    last_id = await queue_service.repo.get_list_message_id(ctx.chat_id)
    if last_id:
        await safe_delete(context.bot, ctx, last_id)

    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    for queue_name in list(queues.keys()):
        ctx.queue_name = queue_name

        last_id = await queue_service.repo.get_queue_message_id(ctx.chat_id, queue_name)
        if last_id:
            await safe_delete(context.bot, ctx, last_id)
        await queue_service.delete_queue(ctx)
