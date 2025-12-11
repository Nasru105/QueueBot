from asyncio import create_task

from telegram import Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.utils.InlineKeyboards import queues_keyboard
from app.utils.utils import delete_later, safe_delete, with_ctx


@with_ctx
async def start_help(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext) -> None:
    """
    Показывает справку по командам.
    """

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

    await context.bot.send_message(chat_id=ctx.chat_id, text=text, message_thread_id=ctx.thread_id)


@with_ctx
async def create(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext) -> None:
    """
    Создаёт новую очередь.
    Имя: из аргументов или автогенерация.
    """

    # Определяем имя очереди
    if context.args:
        queue_name = " ".join(context.args)
    else:
        queue_name = await queue_service.generate_queue_name(ctx.chat_id)

    ctx.queue_name = queue_name

    await queue_service.create_queue(ctx)
    await queue_service.send_queue_message(ctx, context)


@with_ctx
async def queues(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext) -> None:
    """
    Показывает меню со всеми очередями.
    Если нет — временное сообщение.
    """

    # Удаляем старое меню
    last_queues_id = await queue_service.repo.get_list_message_id(ctx.chat_id)
    if last_queues_id:
        await safe_delete(context, ctx, last_queues_id)

    # Получаем очереди
    queues_dict = await queue_service.repo.get_all_queues(ctx.chat_id)
    queue_names = list(queues_dict.keys())

    if queue_names:
        sent = await context.bot.send_message(
            chat_id=ctx.chat_id,
            text="Выберите очередь:",
            reply_markup=await queues_keyboard(queue_names),
            message_thread_id=ctx.thread_id,
        )
        await queue_service.repo.set_list_message_id(ctx.chat_id, sent.message_id)
    else:
        sent = await context.bot.send_message(
            chat_id=ctx.chat_id, text="Нет активных очередей", message_thread_id=ctx.thread_id
        )
        await queue_service.repo.clear_list_message_id(ctx.chat_id)
        create_task(delete_later(context, ctx, sent.message_id, 10))


@with_ctx
async def nickname(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext, global_mode=False) -> None:
    """Устанавливает отображаемое имя пользователя в очередях."""
    user = update.effective_user
    args = context.args
    user_display_name = " ".join(args) if args else None

    if user_display_name:
        await queue_service.set_user_display_name(ctx, user, user_display_name, global_mode)
        response = (
            f"Установлено глобальное отображаемое имя для пользователя {user.username}: {user_display_name}"
            if global_mode
            else f"Установлено отображаемое имя для пользователя {user.username}: {user_display_name} в чате {ctx.chat_title}"
        )
    else:
        user_display_name = await queue_service.clear_user_display_name(ctx, user, global_mode)
        response = (
            f"Сброшено глобальное отображаемое имя на стандартное ({user_display_name})"
            if global_mode
            else f"Сброшено отображаемое имя для {ctx.chat_title} на глобальное ({user_display_name})"
        )

    response_message = await context.bot.send_message(ctx.chat_id, response, message_thread_id=ctx.thread_id)
    create_task(delete_later(context, ctx, response_message.message_id))


async def chat_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Устанавливает никнейм пользователя в очередях."""
    await nickname(update, context, global_mode=False)


async def global_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Устанавливает отображаемое имя пользователя в очередях."""
    await nickname(update, context, global_mode=True)
