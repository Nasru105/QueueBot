# app/handlers/admin_commands.py
from asyncio import create_task
from functools import wraps

from telegram import Chat, Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.services.mongo_storage import log_collection
from app.utils.utils import delete_later, parse_queue_args, safe_delete


def admins_only(func):
    """Декоратор: только админы (или в личных чатах)"""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        chat: Chat = update.effective_chat

        # В личных чатах — всегда разрешено
        if not chat.title:
            return await func(update, context, *args, **kwargs)

        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in ("administrator", "creator"):
            return await func(update, context, *args, **kwargs)

        return None

    return wrapper


@admins_only
async def delete_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat: Chat = update.effective_chat
    message_id: int = update.message.message_id
    chat_title = chat.title or chat.username or "Личный чат"
    message_thread_id = update.message.message_thread_id if update.message else None
    user = update.effective_user
    actor = user.username or "Unknown"
    ctx = ActionContext(chat.id, chat_title, "", actor, message_thread_id)

    await safe_delete(context, ctx, message_id)

    if not context.args:
        error_message = await context.bot.send_message(
            chat.id, "Использование: \n /delete <Имя очереди>", message_thread_id=message_thread_id
        )
        create_task(delete_later(context, ctx, error_message.message_id))
        return

    queue_name = " ".join(context.args)
    queues = await queue_service.repo.get_all_queues(chat.id)
    ctx.queue_name = queue_name
    if queue_name not in queues:
        error_message = await context.bot.send_message(
            chat.id, f"Очередь {queue_name} не найдена.", message_thread_id=message_thread_id
        )
        create_task(delete_later(context, ctx, error_message.message_id))
        return

    # Удаляем сообщение очереди
    last_id = await queue_service.repo.get_queue_message_id(chat.id, queue_name)
    if last_id:
        await safe_delete(context, ctx, last_id)
    # Удаляем очередь
    await queue_service.delete_queue(ctx)

    # Обновляем меню и все очереди
    await queue_service.mass_update_existing_queues(context.bot, ctx)


@admins_only
async def delete_all_queues(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat: Chat = update.effective_chat
    message_id: int = update.message.message_id
    chat_title = chat.title or chat.username or "Личный чат"
    message_thread_id = update.message.message_thread_id if update.message else None
    user = update.effective_user
    actor = user.username or "Unknown"
    ctx = ActionContext(chat.id, chat_title, "", actor, message_thread_id)

    await safe_delete(context, ctx, message_id)

    # Удаляем меню
    last_list_message_id = await queue_service.repo.get_list_message_id(chat.id)
    if last_list_message_id:
        await safe_delete(context, ctx, last_list_message_id)
        await queue_service.repo.clear_list_message_id(chat.id)

    queues = await queue_service.repo.get_all_queues(chat.id)
    for queue_name in list(queues.keys()):
        ctx.queue_name = queue_name
        last_id = await queue_service.repo.get_queue_message_id(chat.id, queue_name)
        if last_id:
            await safe_delete(context, ctx, last_id)
        await queue_service.delete_queue(ctx)


@admins_only
async def insert_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat: Chat = update.effective_chat
    message_id: int = update.message.message_id
    chat_title = chat.title or chat.username or "Личный чат"
    message_thread_id = update.message.message_thread_id if update.message else None
    user = update.effective_user
    actor = user.username or "Unknown"
    ctx = ActionContext(chat.id, chat_title, "", actor, message_thread_id)

    await safe_delete(context, ctx, message_id)

    args = context.args
    if len(args) < 2:
        err = await context.bot.send_message(
            chat.id,
            "Использование: \n /insert <Имя очереди> <Имя пользователя> [позиция]",
            message_thread_id=message_thread_id,
        )
        create_task(delete_later(context, ctx, err.message_id))
        return

    queue_names = list((await queue_service.repo.get_all_queues(chat.id)).keys())
    queue_name, rest = parse_queue_args(args, queue_names)
    ctx.queue_name = queue_name

    if not queue_name:
        err = await context.bot.send_message(chat.id, "Очередь не найдена.", message_thread_id=message_thread_id)
        create_task(delete_later(context, ctx, err.message_id))
        return

    await queue_service.insert_into_queue(ctx, rest)

    await queue_service.update_queue_message(ctx, query_or_update=update, context=context)


@admins_only
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat: Chat = update.effective_chat
    message_id = update.message.message_id
    chat_title = chat.title or chat.username or "Личный чат"
    thread_id = update.message.message_thread_id
    user = update.effective_user
    actor = user.username or "Unknown"
    ctx = ActionContext(chat.id, chat_title, "", actor, thread_id)

    await safe_delete(context, ctx, message_id)

    args = context.args
    if len(args) < 2:
        err = await context.bot.send_message(
            chat.id,
            "Использование:\n /remove <Имя очереди> <Имя пользователя или Позиция>",
            message_thread_id=thread_id,
        )
        create_task(delete_later(context, ctx, err.message_id))
        return

    queue_names = list((await queue_service.repo.get_all_queues(chat.id)).keys())
    queue_name, rest = parse_queue_args(args, queue_names)
    ctx.queue_name = queue_name

    if not queue_name:
        err = await context.bot.send_message(chat.id, "Очередь не найдена.", message_thread_id=thread_id)
        create_task(delete_later(context, ctx, err.message_id))
        return

    removed_name, position, _ = await queue_service.remove_from_queue(ctx, rest)

    if removed_name:
        await queue_service.update_queue_message(ctx, query_or_update=update, context=context)
    else:
        err = await context.bot.send_message(chat.id, "Пользователь не найден в очереди.", message_thread_id=thread_id)
        create_task(delete_later(context, ctx, err.message_id))


@admins_only
async def replace_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat: Chat = update.effective_chat
    chat_title = chat.title or chat.username or "Личный чат"
    message_thread_id = update.message.message_thread_id if update.message else None
    user = update.effective_user
    actor = user.username or "Unknown"
    ctx = ActionContext(chat.id, chat_title, "", actor, message_thread_id)

    await safe_delete(context, ctx, update.message.message_id)

    args = context.args
    if len(args) < 3:
        err = await context.bot.send_message(
            chat.id,
            "Использование:\n/replace <Очередь> <№1> <№2> или /replace <Очередь> <Имя 1> <Имя 2>",
            message_thread_id=message_thread_id,
        )
        create_task(delete_later(context, ctx, err.message_id))
        return

    # --- 1. Парсим имя очереди ---
    queue_names = list((await queue_service.repo.get_all_queues(chat.id)).keys())
    queue_name = None

    queue_name, rest_names = parse_queue_args(args, queue_names)
    ctx.queue_name = queue_name

    if not queue_name:
        error_message = await context.bot.send_message(
            chat_id=chat.id, text="Очередь не найдена.", message_thread_id=message_thread_id
        )
        create_task(delete_later(context, chat, error_message.message_id))
        return

    await queue_service.replace_users_queue(ctx, rest_names)
    await queue_service.update_queue_message(ctx, query_or_update=update, context=context)


@admins_only
async def rename_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat: Chat = update.effective_chat
    message_id: int = update.message.message_id
    chat_title = chat.title or chat.username or "Личный чат"
    message_thread_id = update.message.message_thread_id if update.message else None
    user = update.effective_user
    actor = user.username or "Unknown"
    ctx = ActionContext(chat.id, chat_title, "", actor, message_thread_id)

    await safe_delete(context, ctx, message_id)

    args = context.args
    if len(args) < 2:
        error = await context.bot.send_message(
            chat_id=chat.id,
            text="Использование: /rename <Старое имя> <Новое имя>",
            message_thread_id=update.message.message_thread_id,
        )
        create_task(delete_later(context, ctx, error.message_id, 10))
        return

    queue_names = list((await queue_service.repo.get_all_queues(chat.id)).keys())
    old_name, rest = parse_queue_args(args, queue_names)
    new_name = " ".join(rest).strip()

    if not old_name or not new_name:
        error = await context.bot.send_message(
            chat_id=chat.id,
            text="Укажите старое и новое имя очереди.",
            message_thread_id=update.message.message_thread_id,
        )
        create_task(delete_later(context, ctx, error.message_id))
        return

    if new_name in queue_names:
        error = await context.bot.send_message(
            chat_id=chat.id,
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


@admins_only
async def get_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    chat: Chat = update.effective_chat
    message_id: int = update.message.message_id
    chat_title = chat.title or chat.username or "Личный чат"
    message_thread_id = update.message.message_thread_id if update.message else None
    user = update.effective_user
    actor = user.username or "Unknown"
    ctx = ActionContext(chat.id, chat_title, "", actor, message_thread_id)

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
        msg = await context.bot.send_message(chat.id, part or "Логи пусты.", message_thread_id=message_thread_id)
        create_task(delete_later(context, ctx, msg.message_id, 60))
