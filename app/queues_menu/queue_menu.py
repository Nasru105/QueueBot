import logging

# import traceback
from telegram import Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.queues_menu.inline_keyboards import queue_swap_keyboard, queues_menu_keyboard
from app.services.logger import QueueLogger
from app.utils.utils import safe_delete


async def handle_queue_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext, queue_index: int, action: str
):
    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    queue_names = list(queues.keys())

    if not (0 <= queue_index < len(queues)):
        QueueLogger.log(ctx, "Invalid queue index", level=logging.WARNING)
        return

    ctx.queue_name = queue_names[queue_index]
    query = update.callback_query

    if action == "refresh":
        await queue_service.send_queue_message(ctx, context)

    elif action == "swap":
        await query.edit_message_text(
            text=f"{ctx.queue_name}: Отправить запрос на обмен местом c ...",
            reply_markup=await queue_swap_keyboard(queues[ctx.queue_name]["queue"], queue_index),
        )

    elif action == "delete":
        await delete_queue(ctx, query, context)

    elif action == "back":
        await query.edit_message_text(text="Список очередей", reply_markup=await queues_menu_keyboard(queue_names))


# # Удалить конкретную очередь
# elif action == "delete" and queue_name:
#     if chat.title and not await is_user_admin(context, ctx.chat_id, user_id):
#         error_message = await context.bot.send_message(
#             ctx.chat_id, "Вы не являетесь администратором", message_thread_id=ctx.thread_id
#         )
#         create_task(delete_later(context, ctx, error_message.message_id))
#         return
#     async with get_chat_lock(ctx.chat_id):
#         await delete_queue(ctx, query, context)


async def delete_queue(ctx: ActionContext, query, context: ContextTypes.DEFAULT_TYPE):
    message = query.message

    # Удаляем сообщение очереди
    last_id = await queue_service.repo.get_queue_message_id(ctx.chat_id, ctx.queue_name)
    if last_id:
        await safe_delete(context.bot, ctx, last_id)

    await queue_service.delete_queue(ctx)

    # Обновляем меню очередей
    await queue_service.mass_update_existing_queues(context.bot, ctx, message.message_id)
