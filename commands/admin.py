import random

from telegram import Update
from telegram.ext import ContextTypes
from functools import wraps

from config import STUDENTS_USERNAMES
from services.queue_logger import QueueLogger
from services.queue_manager import queue_manager
from utils.utils import safe_delete, parse_queue_args


def admins_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        chat = update.effective_chat
        member = await context.bot.get_chat_member(chat.id, user_id)
        if not chat.title or member.status in ('administrator', 'creator'):
            return await func(update, context, *args, **kwargs)
        return None

    return wrapper


@admins_only
async def admin_help(update, context):
    chat = update.effective_chat
    message_id = update.message.message_id
    message_thread_id = update.message.message_thread_id
    await safe_delete(context, chat, message_id)

    text = (
        "/create <Имя очереди> - создает очередь\n"
        "/queues - посмотреть активные очереди\n\n"
        "Команды для администраторов:\n"
        "/delete <Имя очереди> - удалить очередь\n"
        "/delete_all - удалить все очереди\n"
        "/insert <Имя очереди> <Имя пользователя> <Индекс> - вставить  <Имя пользователя> на <Индекс> место в очереди\n"
        "/remove <Имя очереди> <Имя пользователя> или <Индекс> - удалить <Имя пользователя> или <Индекс> из очереди\n"
        "/replace <Имя очереди> <Индекс1> <Индекс2> - поменять местами <Индекс1> и <Индекс2> в очереди\n"
        "/rename <Старое имя очереди> <Новое имя очереди> - переименовать очередь\n\n"
        "/generate <Имя очереди> <Подгруппа>\n"
        "/getlist <Имя очереди> <Подгруппа>\n"
    )

    await context.bot.send_message(
        chat_id=chat.id,
        text=text,
        message_thread_id=message_thread_id
    )


@admins_only
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


@admins_only
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


@admins_only
async def insert_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Вставляет пользователя в очередь на указанную позицию.
    Пример: /insert Очередь 1 Иван Иванов 2
    """
    chat = update.effective_chat
    await safe_delete(context, chat, update.message.message_id)

    args = context.args
    if not args:
        return

    queues = list(await queue_manager.get_queues(chat.id))
    queue_name, rest = parse_queue_args(args, queues)
    if not queue_name:
        return

    queue = await queue_manager.get_queue(chat.id, queue_name)

    try:
        position = int(rest[-1]) - 1
        user_name = " ".join(rest[:-1])
    except (ValueError, IndexError):
        position = len(queue)
        user_name = " ".join(rest)

    # Ограничиваем позицию в пределах очереди
    position = max(0, min(position, len(queue)))

    if user_name:
        if user_name in queue:
            remove_position = queue.index(user_name)
            queue.remove(user_name)
            QueueLogger.removed(chat.title or chat.username, queue_name, user_name, remove_position + 1)

        queue.insert(position, user_name)
        QueueLogger.inserted(chat.title or chat.username, queue_name, user_name, position + 1)

    await queue_manager.send_queue_message(update, context, queue_name)



@admins_only
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Удаляет пользователя из очереди по имени или позиции.
    Пример: /remove Очередь 1 Иван Иванов
            /remove Очередь 1 3
    """
    chat = update.effective_chat
    await safe_delete(context, chat, update.message.message_id)

    args = context.args
    if not args:
        return

    queues = list(await queue_manager.get_queues(chat.id))
    queue_name, rest = parse_queue_args(args, queues)
    if not queue_name:
        return

    queue = await queue_manager.get_queue(chat.id, queue_name)

    removed_name = None
    position = None
    # Пробуем удалить по позиции
    try:
        position = int(rest[0]) - 1
        if 0 <= position < len(queue):
            removed_name = queue.pop(position)
        else:
            raise ValueError
    except (ValueError, IndexError):
        user_name = " ".join(rest).strip()
        if user_name in queue:
            position = queue.index(user_name)
            queue.remove(user_name)
            removed_name = user_name

    if removed_name:
        QueueLogger.removed(chat.title or chat.username, queue_name, removed_name, position + 1)
        await queue_manager.send_queue_message(update, context, queue_name)



@admins_only
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
    user_name1 = queue[pos1]
    user_name2 = queue[pos2]
    queue[pos1], queue[pos2] = user_name2, user_name1

    QueueLogger.replaced(chat.title or chat.username, queue_name, user_name1, pos1 + 1, user_name2, pos2 + 1)

    await queue_manager.send_queue_message(update, context, queue_name)


@admins_only
async def get_list_of_students(update: Update, context: ContextTypes.DEFAULT_TYPE, shuffle: bool = False):
    chat = update.effective_chat
    await safe_delete(context, chat, update.message.message_id)

    args = context.args
    subgroup = None

    # Определяем подгруппу, если последний аргумент — A или B
    if args and args[-1].upper() in ("A", "B"):
        subgroup = args.pop(-1).upper()  # удаляем последний элемент

    # Определяем имя очереди
    if args:
        queue_name = " ".join(args)
    else:
        queue_name = await queue_manager.get_queue_name(chat.id)

    # Получаем список студентов
    all_students = list(STUDENTS_USERNAMES.values())
    if shuffle:
        random.shuffle(all_students)

    await queue_manager.create_queue(chat, queue_name)

    # Добавляем в очередь только нужную подгруппу (или всех)
    for username, group in all_students:
        if not subgroup or group == subgroup:
            await queue_manager.add_to_queue(chat, queue_name, username)

    await queue_manager.send_queue_message(update, context, queue_name)


@admins_only
async def generate_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await get_list_of_students(update, context, shuffle=True)


@admins_only
async def rename_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message_id = update.message.message_id

    # Удаляем сообщение с командой, чтобы не засорять чат
    await safe_delete(context, chat, message_id)

    args = context.args
    if not args:
        return  # нет аргументов → ничего не делаем

    # Получаем список всех очередей чата
    queues = list(await queue_manager.get_queues(chat.id))

    old_queue_name, new_queue_name = parse_queue_args(args, queues)
    new_queue_name = " ".join(new_queue_name)

    # Если имя не найдено или новое пустое — ничего не делаем
    if not old_queue_name or not new_queue_name.strip():
        return

    # Переименовываем очередь
    await queue_manager.rename_queue(chat, old_queue_name, new_queue_name)

    # Обновляем сообщение с очередью (уже под новым именем)
    await queue_manager.send_queue_message(update, context, new_queue_name)
