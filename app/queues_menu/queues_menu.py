from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from app.queues.models import ActionContext
from app.queues.service import QueueFacadeService
from app.queues_menu.inline_keyboards import queue_menu_keyboard


async def handle_queues_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext, action: str):
    """
    Обрабатывает нажатие кнопок списка всех очередей (get/delete/hide).
    """
    query = update.callback_query
    queue_service: QueueFacadeService = context.bot_data["queue_service"]

    # Показать очередь
    if action == "get":
        queue = await queue_service.repo.get_queue(ctx.chat_id, ctx.queue_id)
        ctx.queue_name = queue.name
        expiration_time = await queue_service.repo.get_queue_expiration(ctx.chat_id, ctx.queue_id)
        expiration_time = expiration_time.strftime("%d.%m.%Y %H:%M:%S")
        text = escape_markdown(f"Действия с {ctx.queue_name}\n\nУдаление запланировано на {expiration_time}", version=2)
        await query.edit_message_text(
            text=text, parse_mode="MarkdownV2", reply_markup=await queue_menu_keyboard(ctx.queue_id)
        )

    elif action == "hide":
        await queue_service.message_service.hide_queues_list_message(context, ctx, query.message.message_id)
        return
