import re
from functools import wraps

from telegram import Chat, Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.services.argument_parser import ArgumentParser
from app.utils.utils import delete_message_later, is_user_admin, safe_delete, with_ctx


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

        if await is_user_admin(context, ctx.chat_id, user.id):
            return await func(update, context, *args, **kwargs)

        await delete_message_later(context, ctx, "Вы не являетесь администратором")
        return None

    return wrapper


@with_ctx
@admins_only
async def delete_queue(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    if not context.args:
        await delete_message_later(context, ctx, "Использование: \n /delete <Имя очереди>")
        return

    queue_name = " ".join(context.args)
    queue = await queue_service.repo.get_queue_by_name(ctx.chat_id, queue_name)
    ctx.queue_name = queue["name"]
    ctx.queue_id = queue["id"]
    if not queue:
        await delete_message_later(context, ctx, f"Очередь {queue_name} не найдена.")
        return

    # Удаляем сообщение очереди
    last_id = await queue_service.repo.get_queue_message_id(ctx.chat_id, ctx.queue_id)
    if last_id:
        await safe_delete(context.bot, ctx, last_id)

    await queue_service.delete_queue(context, ctx)


@with_ctx
@admins_only
async def delete_all_queues(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    # Удаляем меню
    last_list_message_id = await queue_service.repo.get_list_message_id(ctx.chat_id)
    if last_list_message_id:
        await safe_delete(context.bot, ctx, last_list_message_id)
        await queue_service.repo.clear_list_message_id(ctx.chat_id)

    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    for queue in queues.values():
        ctx.queue_name = queue["name"]
        ctx.queue_id = queue["id"]
        last_id = await queue_service.repo.get_queue_message_id(ctx.chat_id, ctx.queue_id)
        if last_id:
            await safe_delete(context.bot, ctx, last_id)
        await queue_service.delete_queue(context, ctx)


@with_ctx
@admins_only
async def insert_user(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    args = context.args
    if len(args) < 2:
        await delete_message_later(context, ctx, "Использование: \n /insert <Имя очереди> <Имя пользователя> [позиция]")
        return

    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    queue_id, queue_name, rest_args = ArgumentParser.parse_queue_name(args, queues)
    ctx.queue_name = queue_name
    ctx.queue_id = queue_id

    if not queue_name:
        await delete_message_later(context, ctx, "Очередь не найдена.")
        return

    user_name, desired_pos = ArgumentParser.parse_insert_args(rest_args)

    await queue_service.insert_into_queue(ctx, user_name, desired_pos)
    await queue_service.update_queue_message(context, ctx)


@with_ctx
@admins_only
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    args = context.args
    if len(args) < 2:
        await delete_message_later(
            context, ctx, "Использование:\n /remove <Имя очереди> <Имя пользователя или Позиция>"
        )
        return

    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    queue_id, queue_name, rest_args = ArgumentParser.parse_queue_name(args, queues)
    ctx.queue_name = queue_name
    ctx.queue_id = queue_id

    if not queue_name:
        await delete_message_later(context, ctx, "Очередь не найдена.")
        return

    position, user_name = ArgumentParser.parse_remove_args(rest_args)

    removed_name, position = await queue_service.remove_from_queue(ctx, pos=position, user_name=user_name)

    if removed_name:
        await queue_service.update_queue_message(context, ctx)
    else:
        await delete_message_later(context, ctx, "Пользователь не найден в очереди.")


@with_ctx
@admins_only
async def replace_users(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    args = context.args
    if len(args) < 3:
        await delete_message_later(
            context,
            ctx,
            "Использование:\n/replace <Очередь> <Позиция 1> <Позиция 2> или \n/replace <Очередь> <Имя 1> <Имя 2>",
        )
        return

    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    queue_id, queue_name, rest_names = ArgumentParser.parse_queue_name(args, queues)
    ctx.queue_name = queue_name
    ctx.queue_id = queue_id

    if not queue_name:
        await delete_message_later(context, ctx, "Очередь не найдена.")
        return

    members_names = [m.get("display_name") for m in queues[queue_id].get("members", [])]

    pos1, pos2, name1, name2 = ArgumentParser.parse_replace_args(rest_names, members_names)

    await queue_service.replace_users_queue(ctx, pos1, pos2, name1, name2)
    await queue_service.update_queue_message(context, ctx)


@with_ctx
@admins_only
async def rename_queue(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    args = context.args
    if len(args) < 2:
        await delete_message_later(context, ctx, "Использование: /rename <Старое имя> <Новое имя>")
        return

    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    queue_id, old_name, rest_args = ArgumentParser.parse_queue_name(args, queues)
    new_name = " ".join(rest_args).strip()
    ctx.queue_name = old_name
    ctx.queue_id = queue_id

    if not old_name or not new_name:
        await delete_message_later(context, ctx, "Укажите старое и новое имя очереди.")
        return

    if new_name in {queue["name"] for queue in queues.values()}:
        await delete_message_later(context, ctx, f"Очередь с именем '{new_name}' уже существует.")
        return

    await queue_service.rename_queue(ctx, new_name)
    ctx.queue_name = new_name

    await queue_service.update_queue_message(context, ctx)


@with_ctx
@admins_only
async def set_queue_expiration_time(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    """
    Команда для изменения времени автоудаления очереди.
    """
    args = context.args
    if len(args) < 2:
        await delete_message_later(context, ctx, "Использование: /set_expire_time <Очередь> <часы>")
        return

    try:
        hours = int(context.args[-1])
        # Валидация
        if hours < 1:
            await delete_message_later(context, ctx, "Время должно быть не менее 1 часа.")
            return

        queue_name = " ".join(context.args[:-1])
        queue = await queue_service.repo.get_queue_by_name(ctx.chat_id, queue_name)
        ctx.queue_name = queue_name
        ctx.queue_id = queue["id"]

        if not queue:
            await delete_message_later(context, ctx, "Очередь не найдена.")
            return

        ctx.queue_id = queue["id"]

        # Устанавливаем новое время
        await queue_service.auto_cleanup_service.reschedule_expiration(context, ctx, hours * 3600)

        await delete_message_later(
            context, ctx, f"Время автоудаления очереди '{ctx.queue_name}' установлено на {hours} ч."
        )

    except ValueError:
        await delete_message_later(context, ctx, "Неверный формат числа. Введите целое число часов.")


@with_ctx
@admins_only
async def set_queue_description(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    if len(context.args) < 1:
        await delete_message_later(context, ctx, "Использование: \n /set_description <Имя очереди> [описание]")
        return

    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    queue_id, queue_name, rest = ArgumentParser.parse_queue_name(context.args, queues)
    ctx.queue_name = queue_name
    ctx.queue_id = queue_id

    if not queue_name:
        await delete_message_later(context, ctx, "Очередь не найдена.")
        return

    if not rest:
        await queue_service.set_queue_description(ctx, None)
        await queue_service.update_queue_message(context, ctx)
        return

    original_text = update.message.text
    escaped_queue_name = re.escape(queue_name)
    pattern = rf"^/set_description\s+{escaped_queue_name}\s+(.*)"
    match = re.match(pattern, original_text, re.DOTALL)
    if match:
        description = match.group(1)

    await queue_service.set_queue_description(ctx, description)
    await queue_service.update_queue_message(context, ctx)
