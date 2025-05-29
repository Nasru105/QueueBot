import random

from telegram import Update
from telegram.ext import ContextTypes

from config import STUDENTS
from services.queue_service import queues, last_queue_message, save_data, get_last_message_id, set_last_message_id, \
    get_queue_message, get_queue, add_to_queue
from utils.utils import safe_delete, get_queue_keyboard


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Получаем список админов чата
    admins = await context.bot.get_chat_administrators(chat_id)
    # Проверяем, является ли пользователь админом
    return any(admin.user.id == user_id for admin in admins)



async def clear_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    await safe_delete(context, chat_id, message_id)

    if not await is_admin(update, context):
        return

    queues[chat_id] = []

    last_id = get_last_message_id(chat_id)
    await safe_delete(context, chat_id, last_id)

    set_last_message_id(chat_id, None)


async def insert_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    await safe_delete(context, chat_id, message_id)
    message_thread_id = update.message.message_thread_id

    if not await is_admin(update, context):
        return

    args = context.args
    if len(args) < 2:
        return

    name = " ".join(args[:-1])
    try:
        position = int(args[-1]) - 1
    except ValueError as ex:
        print(f"ValueError: {ex}")
        return

    # Получаем или создаём очередь
    q = get_queue(chat_id)

    # Гарантируем допустимую позицию
    if position < 0:
        position = 0
    elif position > len(q):
        position = len(q)

    # Вставляем имя, если его нет
    if name not in q:
        q.insert(position, name)

    # Удаляем старое сообщение об очереди
    last_id = get_last_message_id(chat_id)
    await safe_delete(context, chat_id, last_id)

    # Отправляем новое сообщение об очереди
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=get_queue_message(chat_id),
        reply_markup=get_queue_keyboard(),
        message_thread_id=message_thread_id
    )

    set_last_message_id(chat_id, sent.message_id)


async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    await safe_delete(context, chat_id, message_id)
    message_thread_id = update.message.message_thread_id

    if not await is_admin(update, context):
        return

    args = context.args
    if len(args) < 1:
        return

    name = " ".join(args)

    q = get_queue(chat_id)

    if name in q:
        q.remove(name)

    last_id = get_last_message_id(chat_id)
    await safe_delete(context, chat_id, last_id)

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=get_queue_message(chat_id),
        reply_markup=get_queue_keyboard(),
        message_thread_id=message_thread_id
    )

    set_last_message_id(chat_id, sent.message_id)


async def generate_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    await safe_delete(context, chat_id, message_id)
    message_thread_id = update.message.message_thread_id

    if not await is_admin(update, context):
        return

    # Перемешиваем студентов без повторений
    random_STUDENTS = random.sample(STUDENTS, len(STUDENTS))
    queues[chat_id] = []
    for user in random_STUDENTS:
        add_to_queue(chat_id, user[0])

    last_id = get_last_message_id(chat_id)
    await safe_delete(context, chat_id, last_id)

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=get_queue_message(chat_id),
        reply_markup=get_queue_keyboard(),
        message_thread_id=message_thread_id
    )

    set_last_message_id(chat_id, sent.message_id)


async def generate_a_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    await safe_delete(context, chat_id, message_id)
    message_thread_id = update.message.message_thread_id

    if not await is_admin(update, context):
        return

    # Перемешиваем студентов без повторений
    random_STUDENTS = random.sample(STUDENTS, len(STUDENTS))
    queues[chat_id] = []

    for student in random_STUDENTS:
        if student[1] == "А":
            add_to_queue(chat_id, student[0])

    last_id = get_last_message_id(chat_id)
    await safe_delete(context, chat_id, last_id)

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=get_queue_message(chat_id),
        reply_markup=get_queue_keyboard(),
        message_thread_id=message_thread_id
    )

    set_last_message_id(chat_id, sent.message_id)

async def generate_b_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    await safe_delete(context, chat_id, message_id)
    message_thread_id = update.message.message_thread_id

    if not await is_admin(update, context):
        return

    # Перемешиваем студентов без повторений
    random_STUDENTS = random.sample(STUDENTS, len(STUDENTS))
    queues[chat_id] = []

    for student in random_STUDENTS:
        if student[1] == "Б":
            add_to_queue(chat_id, student[0])

    last_id = get_last_message_id(chat_id)
    await safe_delete(context, chat_id, last_id)

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=get_queue_message(chat_id),
        reply_markup=get_queue_keyboard(),
        message_thread_id=message_thread_id
    )

    set_last_message_id(chat_id, sent.message_id)


