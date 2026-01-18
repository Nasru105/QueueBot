from telegram import Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.queues_menu.inline_keyboards import queues_menu_keyboard
from app.services.argument_parser import ArgumentParser
from app.utils.utils import delete_message_later, safe_delete, with_ctx


@with_ctx
async def create(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext) -> None:
    """
    Создаёт новую очередь.
    Имя: из аргументов или автогенерация.
    """
    flags = {"-h": None}

    args_parts, parsed_flags = ArgumentParser.parse_flags_args(context.args, flags)

    # Определяем имя очереди
    if args_parts:
        queue_name = " ".join(args_parts)
    else:
        queue_name = await queue_service.generate_queue_name(ctx.chat_id)
    ctx.queue_name = queue_name

    try:
        expires_in_seconds = int(parsed_flags["-h"]) * 3600 if parsed_flags.get("-h") else 86400
    except (ValueError, TypeError):
        await delete_message_later(context, ctx, "параметр -h должен быть целым числом, обозначающим часы")
        return

    queue_id = await queue_service.create_queue(context, ctx, expires_in_seconds)
    ctx.queue_id = queue_id

    if not queue_id:
        await delete_message_later(context, ctx, f"Очередь с именем {ctx.queue_name} уже существет")
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
        await safe_delete(context.bot, ctx, last_queues_id)

    # Получаем очереди
    queues = await queue_service.repo.get_all_queues(ctx.chat_id)

    if queues:
        sent = await context.bot.send_message(
            chat_id=ctx.chat_id,
            text="Выберите очередь:",
            reply_markup=await queues_menu_keyboard(queues),
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


@with_ctx
async def chat_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext) -> None:
    """Устанавливает никнейм пользователя в очередях."""
    await nickname(update, context, ctx=ctx, global_mode=False)


@with_ctx
async def global_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext) -> None:
    """Устанавливает отображаемое имя пользователя в очередях."""
    await nickname(update, context, ctx=ctx, global_mode=True)
