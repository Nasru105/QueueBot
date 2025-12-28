import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.queues.models import ActionContext
from app.queues_menu.queue_menu import handle_queue_menu
from app.queues_menu.queues_menu import handle_queues_menu
from app.services.logger import QueueLogger
from app.utils.utils import with_ctx


@with_ctx
async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    """Parse callback payload and dispatch to appropriate controller."""
    query = update.callback_query
    await query.answer()

    try:
        _, menu_type, queue_id, action = query.data.split("|")
        ctx.queue_id = queue_id
    except Exception:
        QueueLogger.log(ctx, "Invalid menu callback", level=logging.WARNING)
        return

    if menu_type == "queue":
        await handle_queue_menu(update, context, ctx, action)
    elif menu_type == "queues":
        await handle_queues_menu(update, context, ctx, action)
    else:
        QueueLogger.log(ctx, f"Unknown menu type: {menu_type}", level=logging.WARNING)
