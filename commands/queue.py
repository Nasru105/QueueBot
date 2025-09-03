from asyncio import create_task
from telegram import Update, Chat
from telegram.ext import ContextTypes
from utils.InlineKeyboards import queues_keyboard
from utils.utils import safe_delete, delete_later
from services.queue_manager import queue_manager

async def start_help(update, context):
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
    )

    await context.bot.send_message(
        chat_id=chat.id,
        text=text,
        message_thread_id=message_thread_id
    )


async def create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Создаёт новую очередь в чате.
    Если имя очереди передано аргументами — используется оно,
    иначе генерируется автоматически на основе количества существующих очередей.
    """
    chat: Chat = update.effective_chat
    message_id: int = update.message.message_id

    # Удаляем команду пользователя
    await safe_delete(context, chat, message_id)

    # Получаем имя очереди
    args = context.args
    if args:
        queue_name = " ".join(args)
    else:
        queue_name = await queue_manager.get_queue_name(chat.id)

    # Создаём очередь и отправляем сообщение с ней
    await queue_manager.create_queue(chat, queue_name)
    await queue_manager.send_queue_message(update, context, queue_name)


async def queues(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Отображает список всех активных очередей в чате.
    Если очередей нет — выводит уведомление и удаляет его через 10 секунд.
    """
    chat: Chat = update.effective_chat
    message_id: int = update.message.message_id
    message_thread_id: int | None = update.message.message_thread_id if update.message else None

    # Удаляем команду пользователя
    await safe_delete(context, chat, message_id)

    # Получаем список активных очередей
    queues_list = await queue_manager.get_queues(chat.id)

    # Удаляем старое сообщение с меню очередей, если оно есть
    last_queues_id = await queue_manager.get_last_queues_message_id(chat.id)
    if last_queues_id:
        await safe_delete(context, chat, last_queues_id)

    if queues_list:
        # Отправляем меню выбора очереди
        sent = await context.bot.send_message(
            chat_id=chat.id,
            text="Выберите очередь:",
            reply_markup=await queues_keyboard(list(queues_list)),
            message_thread_id=message_thread_id
        )
        # Сохраняем ID нового меню
        await queue_manager.set_last_queues_message_id(chat.id, sent.message_id)
    else:
        # Сообщение о том, что очередей нет
        sent = await context.bot.send_message(
            chat_id=chat.id,
            text="Нет активных очередей",
            message_thread_id=message_thread_id
        )
        await queue_manager.set_last_queues_message_id(chat.id, None)

        # Автоматическое удаление сообщения через 10 секунд
        create_task(delete_later(context, chat, sent.message_id, 10))
