from telegram import Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext, Queue
from app.queues.services.swap_service.swap_handler import request_swap, respond_swap


async def swap_router(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext, queue: Queue, args):
    query = update.callback_query
    user = query.from_user
    action, target = args
    members = queue.members
    is_delete = False

    if action == "request" and target:
        is_delete = await request_swap(context, ctx, members, user, target)
    elif action == "accept" and target:
        is_delete = await respond_swap(context, ctx, user, target, accept=True)
        await queue_service.update_queue_message(context, ctx)
    elif action == "decline" and target:
        is_delete = await respond_swap(context, ctx, user, target, accept=False)

    if is_delete:
        await context.bot.delete_message(chat_id=ctx.chat_id, message_id=query.message.message_id)
