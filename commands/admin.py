import random

from telegram import Update
from telegram.ext import ContextTypes
from functools import wraps

from config import STUDENTS_USERNAMES
from services.queue_service import queue_manager
from utils.utils import safe_delete, get_time


def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        chat = update.effective_chat
        member = await context.bot.get_chat_member(chat.id, user_id)
        if member.status in ('administrator', 'creator'):
            return await func(update, context, *args, **kwargs)
        return None

    return wrapper


# @admin_only
async def delete_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message_id = update.message.message_id

    await safe_delete(context, chat, message_id)

    queue_name = " ".join(context.args)
    if not queue_name:
        return

    # Удаляем старое меню очередей, если есть
    last_queues_id = await queue_manager.get_last_queues_message_id(chat.id)
    if last_queues_id:
        await safe_delete(context, chat, last_queues_id)

    last_id = await queue_manager.get_last_queue_message_id(chat.id, queue_name)
    if last_id:
        await safe_delete(context, chat, last_id)

    await queue_manager.delete_queue(chat, queue_name)


# @admin_only
async def delete_queues(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message_id = update.message.message_id

    await safe_delete(context, chat, message_id)

    # Удаляем старое меню очередей, если есть
    last_queues_id = await queue_manager.get_last_queues_message_id(chat.id)
    if last_queues_id:
        await safe_delete(context, chat, last_queues_id)

    queues = await queue_manager.get_queues(chat.id)
    for queue_name in list(queues.keys()):

        last_id = await queue_manager.get_last_queue_message_id(chat.id, queue_name)
        if last_id:
            await safe_delete(context, chat, last_id)

        await queue_manager.delete_queue(chat, queue_name)


# @admin_only
async def insert_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message_id = update.message.message_id

    await safe_delete(context, chat, message_id)

    args = context.args
    if not args:
        return

    list_queues = list(await queue_manager.get_queues(chat.id))
    queue_name = None
    queue = []
    position = None
    name = None

    for sep in range(1, len(args)):
        potential_queue_name = " ".join(args[:sep])
        if potential_queue_name in list_queues:
            queue_name = potential_queue_name
            queue = await queue_manager.get_queue(chat.id, queue_name)
            try:
                position = int(args[-1]) - 1
                name = " ".join(args[sep:-1])
            except ValueError:
                position = len(queue)
                name = " ".join(args[sep:])
            break

    if queue_name is None:
        # Не нашли очередь — можно отправить сообщение об ошибке или просто выйти
        return

    # Корректируем позицию
    position = max(0, min(position, len(queue)))

    if name and name not in queue:
        queue.insert(position, name)
        print(
            f"{get_time()}|{chat.title if chat.title else chat.username}|{queue_name}: insert {name} ({position + 1})",
            flush=True)

    await queue_manager.send_queue_message(update, context, queue_name)


# @admin_only
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message_id = update.message.message_id

    await safe_delete(context, chat, message_id)

    args = context.args
    if not args:
        return

    list_queues = list(await queue_manager.get_queues(chat.id))
    queue_name = None
    queue = []
    name = None
    position = None

    # Ищем имя очереди в первых аргументах
    for sep in range(1, len(args)):
        potential_queue_name = " ".join(args[:sep])
        if potential_queue_name in list_queues:
            queue_name = potential_queue_name
            queue = await queue_manager.get_queue(chat.id, queue_name)
            # Остальные аргументы - либо имя пользователя, либо индекс
            remainder = args[sep:]
            break

    if queue_name is None:
        return

    if not remainder:
        return

    # Пытаемся распарсить позицию
    try:
        position = int(remainder[0]) - 1
        if position < 0 or position >= len(queue):
            raise ValueError
    except ValueError:
        name = " ".join(remainder)

    # Удаляем по позиции, если она допустима
    if position is not None and 0 <= position < len(queue):
        removed_name = queue.pop(position)
        print(
            f"{get_time()}|{chat.title if chat.title else chat.username}|{queue_name}: remove {removed_name} ({position + 1})",
            flush=True)
        await queue_manager.send_queue_message(update, context, queue_name)
    elif name and name in queue:  # Или по имени
        position = queue.index(name)
        queue.remove(name)
        print(
            f"{get_time()}|{chat.title if chat.title else chat.username}|{queue_name}: remove {name} ({position + 1})",
            flush=True)
        await queue_manager.send_queue_message(update, context, queue_name)


# @admin_only
async def replace_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message_id = update.message.message_id

    await safe_delete(context, chat, message_id)

    args = context.args
    if len(args) < 3:
        return

    queue_name = " ".join(args[:-2])
    try:
        pos1, pos2 = sorted(map(lambda x: int(x) - 1, args[-2:]))
    except ValueError:
        return
    queue = await queue_manager.get_queue(chat.id, queue_name)
    if queue is None:
        return

    queue_length = len(queue)
    if (pos1 == pos2 or
            pos1 < 0 or pos2 < 0 or
            pos1 >= queue_length or pos2 >= queue_length):
        return

    # Меняем местами
    name1 = queue[pos1]
    name2 = queue[pos2]
    queue[pos1], queue[pos2] = name2, name1

    print(
        f"{get_time()}|{chat.title if chat.title else chat.username}|{queue_name}: replace {name1} ({pos1 + 1}) with {name2} ({pos2 + 1})",
        flush=True)

    await queue_manager.send_queue_message(update, context, queue_name)


# @admin_only
async def generate_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message_id = update.message.message_id
    await safe_delete(context, chat, message_id)

    # Обработка аргумента подгруппы
    args = context.args
    subgroup = None

    if not args:
        count_queue = await queue_manager.get_count_queues(chat.id)
        queue_name = f"Очередь {count_queue + 1}"

    elif args[-1] and args[-1].upper() in ("A", "B"):
        subgroup = args[-1].upper()
        if len(args) >= 2:
            queue_name = " ".join(args[:-1])
    else:
        queue_name = " ".join(args)

    # Перемешиваем список студентов
    all_students = list(STUDENTS_USERNAMES.values())
    random.shuffle(all_students)

    await queue_manager.create_queue(chat, queue_name)

    # Добавляем пользователей в очередь по фильтру подгруппы (если задана)
    for username, group in all_students:
        if not subgroup or group == subgroup:
            await queue_manager.add_to_queue(chat, queue_name, username)

    await queue_manager.send_queue_message(update, context, queue_name)
