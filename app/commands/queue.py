from telegram import Update
from telegram.ext import ContextTypes

from app.handlers.scheduler import schedule_queue_expiration
from app.queues import queue_service
from app.queues.models import ActionContext
from app.queues_menu.inline_keyboards import queues_menu_keyboard
from app.utils.utils import delete_message_later, parse_flags_args, safe_delete, with_ctx


@with_ctx
async def help_commands(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext) -> None:
    """
    Показывает справку по командам.
    """

    text = (
        "/create [Имя очереди] [-h часы] — создает очередь\n"
        "/queues — посмотреть активные очереди\n"
        "/nickname [nickname] — задает отображаемое имя в текущем чате и  (без парамеров для сброса)\n"
        "/nickname_global [nickname] — задает отображаемое имя для всех чатах (без парамеров для сброса)\n\n"
        "Команды для администраторов:\n"
        "/delete <Имя очереди> — удалить очередь\n"
        "/delete_all — удалить все очереди\n"
        "/insert <Имя очереди> <Имя пользователя> [Позиция] — вставить пользователя на позицию\n"
        "/remove <Имя очереди> <Имя пользователя или Позиция> — удалить из очереди\n"
        "/replace <Имя очереди> <Позиция 1> <Позиция 2> — поменять местами\n"
        "/replace <Имя очереди> <Имя пользователя 1> <Имя пользователя 2> — поменять местами\n"
        "/rename <Старое имя очереди> <Новое имя очереди> — переименовать очередь\n"
        "/set_expire_time <Имя очереди> <часы> — изменение времени автоудаления очереди\n"
    )

    await context.bot.send_message(chat_id=ctx.chat_id, text=text, message_thread_id=ctx.thread_id)


@with_ctx
async def start_help(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext) -> None:
    """
    Показывает справку по командам.
    """

    text = (
        "*Справка по командам QueueBot*\n\n"
        "*Создание очереди:*\n"
        "/create [Имя очереди] [\\-h часы]\n"
        "• Параметр \\-h задаёт срок жизни очереди в часах\\.\n"
        "• Если не указать \\-h, очередь живёт 24 часа\\.\n"
        "• Срок жизни продлевается на 1 час после последнего обновления очереди\\.\n\n"
        "Примеры:\n"
        "/create Очередь 3\n"
        "/create \\-h 3\n"
        "/create Дежурство \\-h 12\n\n"
        "*Просмотр активных очередей:*\n"
        "/queues — показывает все активные очереди в чате\\.\n\n"
        "*Управление отображаемым именем:*\n"
        "/nickname [nickname] — задаёт имя в текущем чате\\. Имеет приоритет над глобальным\\. Без параметров — сброс\\.\n"
        "/nickname\\_global [nickname] — задаёт имя во всех чатах\\. Без параметров — сброс\\.\n\n"
        "*Команды для администраторов:*\n"
        "/delete \\<Имя очереди\\> — удалить очередь\\.\n"
        "/delete\\_all — удалить все очереди\\.\n"
        "/insert \\<Очередь\\> \\<Пользователь\\> [Позиция] — вставить пользователя на позицию\\.\n"
        "/remove \\<Очередь\\> \\<Пользователь или Позиция\\> — удалить пользователя из очереди\\.\n"
        "/replace \\<Очередь\\> \\<Позиция 1\\> \\<Позиция 2\\> — поменять местами позиции\\.\n"
        "/replace \\<Очередь\\> \\<Пользователь 1\\> \\<Пользователь 2\\> — поменять местами пользователей\\.\n"
        "/rename \\<Старое имя очереди\\> \\<Новое имя очереди\\> — переименовать очередь\\.\n"
        "/set\\_expire\\_time \\<Очередь\\> \\<часы\\> — изменение времени автоудаления очереди"
    )

    await context.bot.send_message(
        chat_id=ctx.chat_id,
        text=text,
        message_thread_id=ctx.thread_id,
        parse_mode="MarkdownV2",
        disable_notification=True,
    )


@with_ctx
async def create(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext) -> None:
    """
    Создаёт новую очередь.
    Имя: из аргументов или автогенерация.
    """

    flags = {"-h": None}

    args_parts, parsed_flags = parse_flags_args(context.args, flags)

    # Определяем имя очереди
    if args_parts:
        queue_name = " ".join(args_parts)
    else:
        queue_name = await queue_service.generate_queue_name(ctx.chat_id)

    ctx.queue_name = queue_name

    queue_name = await queue_service.create_queue(ctx)
    if not queue_name:
        await delete_message_later(context, ctx, f"Очередь с именем {ctx.queue_name} уже существет")
    await queue_service.send_queue_message(ctx, context)
    await schedule_queue_expiration(context, ctx, int(parsed_flags["-h"]) * 3600 if parsed_flags["-h"] else 86400)


@with_ctx
async def queues(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext) -> None:
    """
    Показывает меню со всеми очередями.
    Если нет — временное сообщение.
    """

    # Удаляем старое меню
    last_queues_id = await queue_service.repo.get_list_message_id(ctx.chat_id)
    if last_queues_id:
        await safe_delete(context.bot, ctx, last_queues_id)

    # Получаем очереди
    queues_dict = await queue_service.repo.get_all_queues(ctx.chat_id)
    queue_names = list(queues_dict.keys())

    if queue_names:
        sent = await context.bot.send_message(
            chat_id=ctx.chat_id,
            text="Выберите очередь:",
            reply_markup=await queues_menu_keyboard(queue_names),
            message_thread_id=ctx.thread_id,
            disable_notification=True,
        )
        await queue_service.repo.set_list_message_id(ctx.chat_id, sent.message_id)
    else:
        await delete_message_later(context, ctx, "Нет активных очередей")


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

    await delete_message_later(context, ctx, response)


async def chat_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Устанавливает никнейм пользователя в очередях."""
    await nickname(update, context, global_mode=False)


async def global_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Устанавливает отображаемое имя пользователя в очередях."""
    await nickname(update, context, global_mode=True)
