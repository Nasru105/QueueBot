import asyncio
import logging
from typing import List, Optional, Tuple

from services.logger import QueueLogger
from telegram.error import BadRequest


# Безопасное удаление сообщения.
async def safe_delete(context, chat, message_id):
    try:
        await context.bot.delete_message(chat_id=chat.id, message_id=message_id)
    except BadRequest as BREx:
        if BREx.message != "Message to delete not found":
            raise
    except Exception as e:
        QueueLogger.log(
            chat.title or chat.username,
            action=f"Не удалось удалить сообщение {message_id}: {e}",
            level=logging.WARNING,
        )


async def strip_user_name(last_name: str, first_name: str) -> str:
    return f"{last_name.strip() or ''} {first_name.strip() or ''}".strip()


# def get_user_name(user: User):
#     users_names = load_users_names()
#     if user.username in STUDENTS_USERNAMES:
#         name = STUDENTS_USERNAMES[user.username][0]
#     elif user.id in users_names:
#         name = users_names[user.id]
#     else:
#         name = f"{user.first_name} {user.last_name or ''}".strip()
#     return name


async def delete_later(context, chat, message_id, time=5):
    await asyncio.sleep(time)
    await safe_delete(context, chat, message_id)


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
