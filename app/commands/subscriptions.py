from telegram import Chat, Update
from telegram.ext import ContextTypes

from app.queues.models import ActionContext
from app.queues.services.subscription_service import QueueSubscriptionService
from app.utils.utils import delete_message_later, safe_delete


async def _group_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.effective_message
    user = update.effective_user
    if not chat or not message:
        return None
    ctx = ActionContext(
        chat_id=chat.id,
        chat_title=chat.title or str(chat.id),
        thread_id=message.message_thread_id,
    )
    await safe_delete(context.bot, ctx, message.message_id)
    if chat.type not in (Chat.GROUP, Chat.SUPERGROUP):
        await delete_message_later(context, ctx, "Отправьте эту команду в группе, на новые очереди которой хотите подписаться.")
        return None
    if message.sender_chat or not user or user.is_bot:
        await delete_message_later(context, ctx, "Для управления личной подпиской отправьте команду от своего имени.")
        return None
    return user, ctx


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    group_user = await _group_user(update, context)
    if not group_user:
        return
    user, ctx = group_user
    service: QueueSubscriptionService = context.bot_data["subscription_service"]
    created = await service.subscribe(ctx, user.id)
    await delete_message_later(
        context, ctx,
        "Подписка включена. Уведомления о новых очередях этого чата будут приходить в личные сообщения бота."
        if created
        else "Вы уже подписаны на новые очереди этого чата."
    )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    group_user = await _group_user(update, context)
    if not group_user:
        return
    user, ctx = group_user
    service: QueueSubscriptionService = context.bot_data["subscription_service"]
    removed = await service.unsubscribe(ctx.chat_id, user.id)
    await delete_message_later(
        context, ctx,
        "Подписка на новые очереди этого чата отключена."
        if removed
        else "У вас нет подписки на новые очереди этого чата."
    )
