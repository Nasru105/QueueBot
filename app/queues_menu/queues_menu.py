# import traceback
from telegram import Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.queues_menu.inline_keyboards import queue_menu_keyboard


async def handle_queues_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext, action: str):
    """
    Обрабатывает нажатие кнопок списка всех очередей (get/delete/hide).
    """
    query = update.callback_query

    # Показать очередь
    if action == "get":
        queues = await queue_service.repo.get_all_queues(ctx.chat_id)
        queue_name = queues[ctx.queue_id]["name"]
        ctx.queue_name = queue_name

        await query.edit_message_text(
            text=f"Действия с {queue_name}",
            parse_mode="MarkdownV2",
            reply_markup=await queue_menu_keyboard(ctx.queue_id),
        )

    elif action == "hide":
        await queue_service.message_service.hide_queues_list_message(context, ctx)
        return
