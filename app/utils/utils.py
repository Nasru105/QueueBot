import asyncio
import logging
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple

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
        if last_name and first_name
        else user.username
        if user.username
        else str(user.id)
    )


# helper to check presence by user_id
async def has_user(members, user_id, display_name):
    for user in members:
        if user.get("user_id") == user_id:
            return True
        elif user.get("display_name") == display_name:
            user["user_id"] = user_id
            return True
    return False


# Безопасное удаление сообщения.
async def safe_delete(bot, ctx: ActionContext, message_id):
    try:
        await bot.delete_message(chat_id=ctx.chat_id, message_id=message_id)
    except Exception as e:
        await QueueLogger.log(ctx, action=f"Не удалось удалить сообщение {message_id}: {e}", level=logging.WARNING)


async def delete_later(context, ctx, message_id, time=5):
    await asyncio.sleep(time)
    await safe_delete(context.bot, ctx, message_id)


async def delete_message_later(context, ctx, text, time=5, reply_markup=None):
    error_message = await context.bot.send_message(
        ctx.chat_id, text, message_thread_id=ctx.thread_id, reply_markup=reply_markup, disable_notification=True
    )
    task = asyncio.create_task(delete_later(context, ctx, error_message.message_id, time))
    return task


def parse_queue_args(args: list[str], queues: dict[str, dict[str, Any]]) -> tuple[str, str, list[str]]:
    """
    Парсит аргументы команды.
    Ищет САМОЕ ДЛИННОЕ совпадение имени очереди.
    """
    if not args:
        return None, []

    best_match = None
    best_i = 0
    queue_names = {queue["name"]: queue["id"] for queue in queues.values()}
    for i in range(1, len(args) + 1):
        candidate = " ".join(args[:i])
        if candidate in queue_names:
            best_match = candidate
            best_i = i

    if best_match:
        return queue_names[best_match], best_match, args[best_i:]
    return None, None, []


def parse_users_names(args: List[str], members: List[dict]) -> Tuple[Optional[str], Optional[str]]:
    """
    Ищет два имени в очереди из аргументов.
    Возвращает (имя1, имя2) или (None, None)
    """
    if len(args) < 2:
        return None, None

    # Извлекаем все имена из очереди
    queue_names = [user["display_name"] for user in members]

    # Пробуем найти два разных имени
    for i in range(len(args) - 1):
        name1 = " ".join(args[: i + 1])
        name2 = " ".join(args[i + 1 :])

        if name1 in queue_names and name2 in queue_names and name1 != name2:
            return name1, name2

    return None, None


async def is_user_admin(context, chat_id, user_id) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def get_now():
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


async def get_now_formatted_time():
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


def parse_flags_args(args: List[str], target_flags: Dict[str, str]) -> Tuple[List[str], Dict[str, str]]:
    """
    Универсальный разбор аргументов:
    - флаги вида '-h 12'
    - слитные флаги '-h12'
    - любое число флагов
    - сохраняет порядок обычных аргументов

    Возвращает:
        (обычные_аргументы, словарь_флагов)
    """

    args_parts = []
    skip_next = False

    # Множество ключей флагов для быстрого поиска
    flag_keys = set(target_flags.keys())

    for i, part in enumerate(args):
        if skip_next:
            skip_next = False
            continue

        # 1. Флаг формата "-h"
        if part in flag_keys:
            if i + 1 < len(args):
                target_flags[part] = args[i + 1]
                skip_next = True
                continue
            else:
                raise ValueError(f"После флага '{part}' нужно указать значение")

        # 2. Флаг формата "-h12"
        for flag in flag_keys:
            if part.startswith(flag) and len(part) > len(flag):
                value = part[len(flag) :]
                target_flags[flag] = value
                break
        else:
            # 3. Обычный аргумент
            args_parts.append(part)

    return args_parts, target_flags
