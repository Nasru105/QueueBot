# app/handlers/admin_commands.py
from asyncio import create_task
from functools import wraps

from telegram import Chat, Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.services.mongo_storage import log_collection
from app.utils.utils import delete_later, is_user_admin, parse_queue_args, safe_delete, with_ctx


def admins_only(func):
    """Декоратор: только админы (или в личных чатах)"""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        ctx: ActionContext = kwargs.get("ctx")
        user = update.effective_user
        chat: Chat = update.effective_chat

        # В личных чатах — всегда разрешено
        if not chat.title:
            return await func(update, context, *args, **kwargs)

        if is_user_admin(context, ctx.chat_id, user.id):
            return await func(update, context, *args, **kwargs)
        error_message = await context.bot.send_message(
            ctx.chat_id, "Вы не являетесь администратором", message_thread_id=ctx.thread_id
        )
        create_task(delete_later(context, ctx, error_message.message_id))
        return None

    return wrapper


@with_ctx
@admins_only
async def delete_queue(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    if not context.args:
        error_message = await context.bot.send_message(
            ctx.chat_id, "Использование: \n /delete <Имя очереди>", message_thread_id=ctx.thread_id
        )
        create_task(delete_later(context, ctx, error_message.message_id))
        return

    queue_name = " ".join(context.args)
    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    ctx.queue_name = queue_name
    if queue_name not in queues:
        error_message = await context.bot.send_message(
            ctx.chat_id, f"Очередь {queue_name} не найдена.", message_thread_id=ctx.thread_id
        )
        create_task(delete_later(context, ctx, error_message.message_id))
        return

    # Удаляем сообщение очереди
    last_id = await queue_service.repo.get_queue_message_id(ctx.chat_id, queue_name)
    if last_id:
        await safe_delete(context, ctx, last_id)
    # Удаляем очередь
    await queue_service.delete_queue(ctx)

    # Обновляем меню и все очереди
    await queue_service.mass_update_existing_queues(context.bot, ctx)


@with_ctx
@admins_only
async def delete_all_queues(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    # Удаляем меню
    last_list_message_id = await queue_service.repo.get_list_message_id(ctx.chat_id)
    if last_list_message_id:
        await safe_delete(context, ctx, last_list_message_id)
        await queue_service.repo.clear_list_message_id(ctx.chat_id)

    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    for queue_name in list(queues.keys()):
        ctx.queue_name = queue_name
        last_id = await queue_service.repo.get_queue_message_id(ctx.chat_id, queue_name)
        if last_id:
            await safe_delete(context, ctx, last_id)
        await queue_service.delete_queue(ctx)


@with_ctx
@admins_only
async def insert_user(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    args = context.args
    if len(args) < 2:
        err = await context.bot.send_message(
            ctx.chat_id,
            "Использование: \n /insert <Имя очереди> <Имя пользователя> [позиция]",
            message_thread_id=ctx.thread_id,
        )
        create_task(delete_later(context, ctx, err.message_id))
        return

    queue_names = list((await queue_service.repo.get_all_queues(ctx.chat_id)).keys())
    queue_name, rest = parse_queue_args(args, queue_names)
    ctx.queue_name = queue_name

    if not queue_name:
        err = await context.bot.send_message(ctx.chat_id, "Очередь не найдена.", message_thread_id=ctx.thread_id)
        create_task(delete_later(context, ctx, err.message_id))
        return

    await queue_service.insert_into_queue(ctx, rest)

    await queue_service.update_queue_message(ctx, query_or_update=update, context=context)


@with_ctx
@admins_only
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    args = context.args
    if len(args) < 2:
        err = await context.bot.send_message(
            ctx.chat_id,
            "Использование:\n /remove <Имя очереди> <Имя пользователя или Позиция>",
            message_thread_id=ctx.thread_id,
        )
        create_task(delete_later(context, ctx, err.message_id))
        return

    queue_names = list((await queue_service.repo.get_all_queues(ctx.chat_id)).keys())
    queue_name, rest = parse_queue_args(args, queue_names)
    ctx.queue_name = queue_name

    if not queue_name:
        err = await context.bot.send_message(ctx.chat_id, "Очередь не найдена.", message_thread_id=ctx.thread_id)
        create_task(delete_later(context, ctx, err.message_id))
        return

    removed_name, position, _ = await queue_service.remove_from_queue(ctx, rest)

    if removed_name:
        await queue_service.update_queue_message(ctx, query_or_update=update, context=context)
    else:
        err = await context.bot.send_message(
            ctx.chat_id, "Пользователь не найден в очереди.", message_thread_id=ctx.thread_id
        )
        create_task(delete_later(context, ctx, err.message_id))


@with_ctx
@admins_only
async def replace_users(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    await safe_delete(context, ctx, update.message.message_id)

    args = context.args
    if len(args) < 3:
        err = await context.bot.send_message(
            ctx.chat_id,
            "Использование:\n/replace <Очередь> <№1> <№2> или /replace <Очередь> <Имя 1> <Имя 2>",
            message_thread_id=ctx.thread_id,
        )
        create_task(delete_later(context, ctx, err.message_id))
        return

    # --- 1. Парсим имя очереди ---
    queue_names = list((await queue_service.repo.get_all_queues(ctx.chat_id)).keys())
    queue_name = None

    queue_name, rest_names = parse_queue_args(args, queue_names)
    ctx.queue_name = queue_name

    if not queue_name:
        error_message = await context.bot.send_message(
            chat_id=ctx.chat_id, text="Очередь не найдена.", message_thread_id=ctx.thread_id
        )
        create_task(delete_later(context, ctx, error_message.message_id))
        return

    await queue_service.replace_users_queue(ctx, rest_names)
    await queue_service.update_queue_message(ctx, query_or_update=update, context=context)


@with_ctx
@admins_only
async def rename_queue(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    args = context.args
    if len(args) < 2:
        error = await context.bot.send_message(
            chat_id=ctx.chat_id,
            text="Использование: /rename <Старое имя> <Новое имя>",
            message_thread_id=update.message.message_thread_id,
        )
        create_task(delete_later(context, ctx, error.message_id, 10))
        return

    queue_names = list((await queue_service.repo.get_all_queues(ctx.chat_id)).keys())
    old_name, rest = parse_queue_args(args, queue_names)
    new_name = " ".join(rest).strip()

    if not old_name or not new_name:
        error = await context.bot.send_message(
            chat_id=ctx.chat_id,
            text="Укажите старое и новое имя очереди.",
            message_thread_id=update.message.message_thread_id,
        )
        create_task(delete_later(context, ctx, error.message_id))
        return

    if new_name in queue_names:
        error = await context.bot.send_message(
            chat_id=ctx.chat_id,
            text="Очередь с новым именем уже существует.",
            message_thread_id=update.message.message_thread_id,
        )
        create_task(delete_later(context, ctx, error.message_id))
        return
    ctx.queue_name = old_name
    await queue_service.rename_queue(ctx, new_name)
    ctx.queue_name = new_name

    # Обновляем сообщение для новой очереди
    await queue_service.update_queue_message(ctx, query_or_update=update, context=context)


@with_ctx
@admins_only
async def get_logs(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    MAX_LEN = 4000  # чуть меньше лимита 4096

    def format_log(log: dict) -> str:
        lines = []
        lines.append(f"📄 {log.get('asctime', '?')}")
        lines.append(f"🔹 {log.get('message', '')}")

        chat_title = log.get("chat_title")
        queue = log.get("queue")
        actor = log.get("actor")

        info_line = []
        if chat_title:
            info_line.append(chat_title)
        if queue:
            info_line.append(queue)

        if info_line:
            lines.append("🏷️ " + " | ".join(info_line))

        if actor:
            lines.append(f"👤 {actor}")

        return "\n".join(lines)

    def split_text(text: str, max_len: int = MAX_LEN) -> list[str]:
        """Разбивает текст на части, чтобы не превышать лимит Telegram."""
        parts = []
        while len(text) > max_len:
            cut = text.rfind("\n──────────────\n", 0, max_len)  # разрезать по логам
            if cut == -1:
                cut = max_len
            parts.append(text[:cut])
            text = text[cut:]
        parts.append(text)
        return parts

    message_id: int = update.message.message_id

    await safe_delete(context, ctx, message_id)

    args = context.args
    try:
        count = int(args[-1])
    except Exception:
        count = 10

    cursor = log_collection.find().sort("_id", -1).limit(count)
    logs = await cursor.to_list(length=count)

    formatted = "\n──────────────\n".join(format_log(log) for log in logs)

    # 🔥 Разбиваем на части
    parts = split_text(formatted)

    # 📨 Отправляем по очереди
    for part in parts:
        msg = await context.bot.send_message(ctx.chat_id, part or "Логи пусты.", message_thread_id=ctx.thread_id)
        create_task(delete_later(context, ctx, msg.message_id, 60))
