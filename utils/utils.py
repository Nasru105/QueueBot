import asyncio
from typing import List, Optional

from telegram import User

from config import STUDENTS_USERNAMES
from services.queue_logger import QueueLogger
from utils.InlineKeyboards import queue_keyboard


# Безопасное удаление сообщения.
async def safe_delete(context, chat, message_id):
    try:
        await context.bot.delete_message(chat_id=chat.id, message_id=message_id)
    except Exception as e:
        QueueLogger.log(chat.title or chat.username, action=f"Не удалось удалить сообщение {message_id}: {e}")


def get_user_name(user: User):
    if user.username in STUDENTS_USERNAMES:
        name = STUDENTS_USERNAMES[user.username][0]
    else:
        name = f"{user.first_name} {user.last_name or ''}".strip()
    return name


async def delete_later(context, chat, message_id, time=5):
    await asyncio.sleep(time)
    await safe_delete(context, chat, message_id)


def parse_queue_args(args: list[str], queues: list[str]) -> tuple[Optional[str], list[str]]:
    """
    Парсит аргументы команды.
    Ищет совпадение имени очереди среди аргументов
    и возвращает (queue_name, остальные аргументы).

    :param args: Список аргументов команды
    :param queues: список существующих очередей
    :return: (queue_name, other_args) или (None, [])
    """
    for i in range(1, len(args) + 1):
        candidate = " ".join(args[:i])
        if candidate in queues:
            return candidate, args[i:]
    return None, []

async def update_existing_queues_info(bot,queue_manager, chat, queues):
    """
    Обновление сообщений с очередями
    """
    for queue_index, (current_queue_name, queue_data) in enumerate(queues.items()):
        message_id = queue_data.get("last_queue_message_id")

        if message_id:
            # Правильный способ получения сообщения по ID в python-telegram-bot
            await bot.edit_message_text(
                chat_id=chat.id,
                message_id=message_id,
                text=await queue_manager.get_queue_text(chat.id, current_queue_name),
                parse_mode="MarkdownV2",
                reply_markup=queue_keyboard(queue_index),
            )

