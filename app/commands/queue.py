from asyncio import create_task

from telegram import Chat, Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.utils.InlineKeyboards import queues_keyboard
from app.utils.utils import delete_later, safe_delete


async def start_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Показывает справку по командам.
    """
    chat: Chat = update.effective_chat
    message_id = update.message.message_id
    message_thread_id = update.message.message_thread_id
    chat_title = chat.title or chat.username or "Личный чат"

    ctx = ActionContext(
        chat.id, chat_title, queue_name=None, actor=update.effective_user.username, thread_id=message_thread_id
    )

    await safe_delete(context, ctx, message_id)

    text = (
        "/create [Имя очереди] — создает очередь\n"
        "/queues — посмотреть активные очереди\n"
        "/nickname [nickname] — задает отображаемое имя в текущем чате и имеет приоритет над глобальным (без парамеров для сброса)\n"
        "/nickname_global [nickname] — задает отображаемое имя для всех чатах (без парамеров для сброса)\n\n"
        "Команды для администраторов:\n"
        "/delete <Имя очереди> — удалить очередь\n"
        "/delete_all — удалить все очереди\n"
        "/insert <Имя очереди> <Имя пользователя> [Позиция] — вставить пользователя на позицию\n"
        "/remove <Имя очереди> <Имя пользователя или Позиция> — удалить из очереди\n"
        "/replace <Имя очереди> <Позиция 1> <Позиция 2> — поменять местами\n"
        "/replace <Имя очереди> <Имя пользователя 1> <Имя пользователя 2> — поменять местами\n"
        "/rename <Старое имя очереди> <Новое имя очереди> — переименовать очередь\n\n"
    )

    await context.bot.send_message(chat_id=chat.id, text=text, message_thread_id=message_thread_id)


async def create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Создаёт новую очередь.
    Имя: из аргументов или автогенерация.
    """
    chat: Chat = update.effective_chat
    message_id: int = update.message.message_id
    chat_title = chat.title or chat.username or "Личный чат"
    message_thread_id = update.message.message_thread_id if update.message else None
    user = update.effective_user
    actor = user.username or "Unknown"
    ctx = ActionContext(chat.id, chat_title, "", actor, message_thread_id)

    # Удаляем команду
    await safe_delete(context, ctx, message_id)

    # Определяем имя очереди
    if context.args:
        queue_name = " ".join(context.args)
    else:
        queue_name = await queue_service.generate_queue_name(chat.id)

    ctx.queue_name = queue_name

    await queue_service.create_queue(ctx)
    await queue_service.send_queue_message(ctx, context)


async def queues(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Показывает меню со всеми очередями.
    Если нет — временное сообщение.
    """
    chat: Chat = update.effective_chat
    message_id: int = update.message.message_id
    chat_title = chat.title or chat.username or "Личный чат"
    message_thread_id = update.message.message_thread_id if update.message else None
    user = update.effective_user
    actor = user.username or "Unknown"
    ctx = ActionContext(chat.id, chat_title, "", actor, message_thread_id)

    # Удаляем команду
    await safe_delete(context, ctx, message_id)

    # Удаляем старое меню
    last_queues_id = await queue_service.repo.get_list_message_id(chat.id)
    if last_queues_id:
        await safe_delete(context, ctx, last_queues_id)

    # Получаем очереди
    queues_dict = await queue_service.repo.get_all_queues(chat.id)
    queue_names = list(queues_dict.keys())

    if queue_names:
        sent = await context.bot.send_message(
            chat_id=chat.id,
            text="Выберите очередь:",
            reply_markup=await queues_keyboard(queue_names),
            message_thread_id=message_thread_id,
        )
        await queue_service.repo.set_list_message_id(chat.id, sent.message_id)
    else:
        sent = await context.bot.send_message(
            chat_id=chat.id,
            text="Нет активных очередей",
            message_thread_id=message_thread_id,
        )
        await queue_service.repo.clear_list_message_id(chat.id)
        create_task(delete_later(context, ctx, sent.message_id, 10))


async def nickname(update: Update, context: ContextTypes.DEFAULT_TYPE, global_mode=False) -> None:
    """Устанавливает отображаемое имя пользователя в очередях."""
    chat: Chat = update.effective_chat
    message_id: int = update.message.message_id
    chat_title = chat.title or chat.username or "Личный чат"
    message_thread_id = update.message.message_thread_id if update.message else None
    user = update.effective_user
    actor = user.username or "Unknown"
    ctx = ActionContext(chat.id, chat_title, "", actor, message_thread_id)

    await safe_delete(context, ctx, message_id)
    args = context.args
    nickname = " ".join(args) if args else None

    if nickname:
        await queue_service.set_user_display_name(ctx, user, nickname, global_mode)
        response = (
            f"Установлено глобальное отображаемое имя для пользователя {user.username}: {nickname}"
            if global_mode
            else f"Установлено отображаемое имя для пользователя {user.username}: {nickname} в чате {chat_title}"
        )
    else:
        await queue_service.clear_user_display_name(ctx, user, global_mode)
        response = (
            "Сброшено глобальное отображаемое имя на стандартное"
            if global_mode
            else f"Сброшено отображаемое имя для {chat_title} на стандартное"
        )

    response_message = await context.bot.send_message(chat.id, response, message_thread_id=message_thread_id)
    create_task(delete_later(context, ctx, response_message.message_id))


async def chat_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Устанавливает никнейм пользователя в очередях."""
    await nickname(update, context, global_mode=False)


async def global_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Устанавливает отображаемое имя пользователя в очередях."""
    await nickname(update, context, global_mode=True)
