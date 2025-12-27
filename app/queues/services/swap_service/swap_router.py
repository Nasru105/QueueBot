from telegram import Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.queues.services.swap_service.swap_handler import request_swap, respond_swap


async def swap_router(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext, queue, args):
    query = update.callback_query
    user = query.from_user
    action, target = args
    members = queue.get("members", [])

    if action == "request" and target:
        await request_swap(context, ctx, members, user, target)
    elif action == "accept" and target:
        res = await respond_swap(context, ctx, user, target, accept=True)
    elif action == "decline" and target:
        res = await respond_swap(context, ctx, user, target, accept=False)

    if res:
        await context.bot.delete_message(chat_id=ctx.chat_id, message_id=query.message.message_id)
    await queue_service.message_service.hide_queues_list_message(context, ctx, query.message.message_id)
