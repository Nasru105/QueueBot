from telegram import Update
from telegram.ext import ContextTypes

from app.queues.models import ActionContext
from app.queues.service import QueueFacadeService
from app.queues.services.swap_service.swap_router import swap_router
from app.services.locks import get_chat_lock
from app.utils.utils import has_user, with_ctx


@with_ctx
async def queue_router(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    """
    Обрабатывает нажатие кнопок для конкретной очереди.
    """
    query = update.callback_query
    await query.answer()
    user = query.from_user

    args = query.data.split("|")
    _, queue_id, action = args[0:3]
    rest_args = args[3:]

    queue_service: QueueFacadeService = context.bot_data["queue_service"]
    queue = await queue_service.repo.get_queue(ctx.chat_id, queue_id)
    ctx.queue_name = queue.name
    ctx.queue_id = queue_id

    async with get_chat_lock(ctx.chat_id):
        members = queue.members
        display_name = await queue_service.get_user_display_name(user, ctx.chat_id)
        if action == "join":
            if not has_user(members, user.id, display_name):
                await queue_service.join_to_queue(ctx, user)
        elif action == "leave":
            if has_user(members, user.id, display_name):
                await queue_service.leave_from_queue(ctx, user)
        elif action == "swap":
            await swap_router(update, context, ctx, queue, rest_args)
            return

        await queue_service.update_queue_message(context, ctx)
