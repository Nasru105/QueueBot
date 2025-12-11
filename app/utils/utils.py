import asyncio
import logging
from functools import wraps
from typing import List, Optional, Tuple

from telegram import Chat, Update, User
from telegram.ext import ContextTypes

from app.queues.models import ActionContext
from app.services.logger import QueueLogger


def with_ctx(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat: Chat = update.effective_chat
        user = update.effective_user

        ctx = ActionContext(
            chat_id=chat.id,
            chat_title=chat.title or chat.username or "Личный чат",
            queue_name="",
            actor=user.username or "Unknown",
            thread_id=update.message.message_thread_id if update.message else None,
        )

        if update.message:
            message_id: int = update.message.message_id
            await safe_delete(context, ctx, message_id)

        kwargs["ctx"] = ctx
        return await func(update, context, *args, **kwargs)

    return wrapper


# Безопасное удаление сообщения.
async def safe_delete(context, ctx: ActionContext, message_id):
    try:
        await context.bot.delete_message(chat_id=ctx.chat_id, message_id=message_id)
    except Exception as e:
        QueueLogger.log(ctx, action=f"Не удалось удалить сообщение {message_id}: {e}", level=logging.WARNING)


def strip_user_full_name(user: User) -> str:
    last_name = user.last_name.strip() if user.last_name else ""
    first_name = user.first_name.strip() if user.first_name else ""
    return (
        f"{last_name} {first_name}".strip()
        if last_name and first_name
        else user.username
        if user.username
        else str(user.id)
    )


async def delete_later(context, ctx, message_id, time=5):
    await asyncio.sleep(time)
    await safe_delete(context, ctx, message_id)


# app/queues_service/__init__.py или utils
def parse_queue_args(args: list[str], queues: list[str]) -> tuple[Optional[str], list[str]]:
    """
    Парсит аргументы команды.
    Ищет САМОЕ ДЛИННОЕ совпадение имени очереди.
    """
    if not args:
        return None, []

    best_match = None
    best_i = 0

    for i in range(1, len(args) + 1):
        candidate = " ".join(args[:i])
        if candidate in queues:
            best_match = candidate
            best_i = i

    if best_match:
        return best_match, args[best_i:]
    return None, []


def parse_users_names(args: List[str], queue: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Ищет два имени в очереди из аргументов.
    Возвращает (имя1, имя2) или (None, None)
    """
    if len(args) < 2:
        return None, None

    # Пробуем найти два разных имени
    for i in range(len(args) - 1):
        name1 = " ".join(args[: i + 1])
        name2 = " ".join(args[i + 1 :])

        if name1 in queue and name2 in queue and name1 != name2:
            return name1, name2

    return None, None


async def is_user_admin(context, chat_id, user_id) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False
