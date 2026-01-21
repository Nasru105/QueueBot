import asyncio
from datetime import datetime
from functools import wraps
from typing import List

from telegram import Chat, Update, User
from telegram.ext import ContextTypes

from app.queues.models import ActionContext, Member
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
            actor=user.username or strip_user_full_name(user),
            thread_id=update.message.message_thread_id
            if update.message
            else update.callback_query.message.message_thread_id,
        )

        if update.message:
            message_id: int = update.message.message_id
            await safe_delete(context.bot, ctx, message_id)

        kwargs["ctx"] = ctx
        return await func(update, context, *args, **kwargs)

    return wrapper


def strip_user_full_name(user: User) -> str:
    last_name = user.last_name.strip() if user.last_name else ""
    first_name = user.first_name.strip() if user.first_name else ""
    return (
        f"{last_name} {first_name}".strip()
        if last_name or first_name
        else user.username
        if user.username
        else str(user.id)
    )


# helper to check presence by user_id
def has_user(members: List[Member], user_id, display_name):
    for user in members:
        if user.user_id == user_id:
            return True
        elif user.display_name == display_name and not user.user_id:
            user.user_id = user_id
            return True
    return False


# Безопасное удаление сообщения.
async def safe_delete(bot, ctx: ActionContext, message_id):
    try:
        await bot.delete_message(chat_id=ctx.chat_id, message_id=message_id)
    except Exception as e:
        await QueueLogger.log(ctx, action=f"Не удалось удалить сообщение {message_id}: {e}", level="WARNING")


async def delete_later(context, ctx, message_id, time=5):
    await asyncio.sleep(time)
    await safe_delete(context.bot, ctx, message_id)


async def delete_message_later(context, ctx, text, time=5, reply_markup=None):
    error_message = await context.bot.send_message(
        ctx.chat_id, text, message_thread_id=ctx.thread_id, reply_markup=reply_markup, disable_notification=True
    )
    task = asyncio.create_task(delete_later(context, ctx, error_message.message_id, time))
    return task


async def is_user_admin(context, chat_id, user_id) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


def get_now():
    # Возвращает datetime объект текущего времени (локальное)
    return datetime.now()


def parse_time_str(s: str) -> datetime:
    """Парсит строку формата "%d.%m.%Y %H:%M:%S" в datetime.

    Если передан уже datetime — возвращает как есть.
    """
    if isinstance(s, datetime):
        return s
    # поддержим старый формат хранения
    return datetime.strptime(s, "%d.%m.%Y %H:%M:%S")


def get_now_formatted_time():
    # Текущее время
    now = datetime.now()
    formatted_time = now.strftime("%d.%m.%Y %H:%M:%S")
    return formatted_time


def split_text(text: str, end="\n──────────────\n", max_len: int = 4000) -> list[str]:
    """Разбивает текст на части, чтобы не превышать лимит Telegram."""
    parts = []
    while len(text) > max_len:
        cut = text.rfind(end, 0, max_len)  # разрезать по логам
        if cut == -1:
            cut = max_len
        parts.append(text[:cut])
        text = text[cut:]
    parts.append(text)
    return parts
