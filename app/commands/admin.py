# app/handlers/admin_commands.py
from asyncio import create_task
from functools import wraps

from telegram import Chat, Update
from telegram.ext import ContextTypes

from app.queue_service import queue_service
from app.queue_service.queue_service import ActionContext
from app.services.logger import QueueLogger
from app.utils.utils import delete_later, parse_queue_args, parse_users_names, safe_delete


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
async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message_id = update.message.message_id
    chat_title = chat.title or chat.username or "Личный чат"
    message_thread_id = update.message.message_thread_id
    ctx = ActionContext(chat.id, chat_title, thread_id=message_thread_id)

    await safe_delete(context, ctx, message_id)

    text = (
        "/create [Имя очереди] — создает очередь\n"
        "/queues — посмотреть активные очереди\n"
        "/nickname [nickname] — задает отображаемое имя в чате и имеет приоритет над глобальным (без парамеров для сброса)\n"
        "/nickname_global [nickname] — задает отображаемое всех чатах (без парамеров для сброса)\n\n"
        "Команды для администраторов:\n"
        "/delete <Имя очереди> — удалить очередь\n"
        "/delete_all — удалить все очереди\n"
        "/insert <Имя очереди> <Имя пользователя> [Позиция] — вставить пользователя на позицию\n"
        "/remove <Имя очереди> <Имя пользователя или Позиция> — удалить из очереди\n"
        "/replace <Имя очереди> <Позиция 1> <Позиция 2> — поменять местами\n"
        "/replace <Имя очереди> <Имя пользователя 1> <Имя пользователя 2> — поменять местами\n"
        "/rename <Старое имя очереди> <Новое имя очереди> — переименовать очередь\n\n"
        "/generate <Имя очереди> <A|B> — сгенерировать из списка (перемешать)\n"
        "/getlist <Имя очереди> <A|B> — просто добавить без перемешивания\n"
    )

    await context.bot.send_message(chat_id=chat.id, text=text, message_thread_id=message_thread_id)


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
    await queue_service.update_existing_queues_info(context.bot, ctx)


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
    message_id: int = update.message.message_id
    chat_title = chat.title or chat.username or "Личный чат"
    message_thread_id = update.message.message_thread_id if update.message else None
    user = update.effective_user
    actor = user.username or "Unknown"
    ctx = ActionContext(chat.id, chat_title, "", actor, message_thread_id)

    await safe_delete(context, ctx, message_id)

    args = context.args
    if len(args) < 3:
        error_msg = "Использование:\n/replace <Очередь> <№1> <№2>\nили\n/replace <Очередь> <Имя 1> <Имя 2>"
        error_message = await context.bot.send_message(
            chat_id=chat.id, text=error_msg, message_thread_id=message_thread_id
        )
        create_task(delete_later(context, chat, error_message.message_id))
        return

    queue_name = None
    pos1 = pos2 = None
    user_name_1 = user_name_2 = None

    # Попытка: по позициям
    try:
        pos1 = int(args[-2]) - 1
        pos2 = int(args[-1]) - 1
        queue_name = " ".join(args[:-2])
        mode = "positions"
    except ValueError:
        mode = "names"

    if mode == "names":
        # Режим: по именам
        queue_names = list((await queue_service.repo.get_all_queues(chat.id)).keys())
        queue_name, rest = parse_queue_args(args, queue_names)

        if not queue_name:
            error_message = await context.bot.send_message(
                chat_id=chat.id, text="Очередь не найдена.", message_thread_id=message_thread_id
            )
            create_task(delete_later(context, chat, error_message.message_id))
            return

        queue = await queue_service.repo.get_queue(chat.id, queue_name)
        user_name_1, user_name_2 = parse_users_names(rest, queue)

        if not user_name_1 or not user_name_2:
            error_message = await context.bot.send_message(
                chat_id=chat.id,
                text=f"Один или оба пользователя не найдены в очереди «{queue_name}».",
                message_thread_id=message_thread_id,
            )
            create_task(delete_later(context, chat, error_message.message_id))
            return

        pos1 = queue.index(user_name_1)
        pos2 = queue.index(user_name_2)

    else:
        # Режим: по позициям
        if not queue_name.strip():
            error_message = await context.bot.send_message(
                chat_id=chat.id, text="Укажите имя очереди.", message_thread_id=message_thread_id
            )
            create_task(delete_later(context, chat, error_message.message_id))
            return

        if pos1 < 0 or pos2 < 0:
            error_message = await context.bot.send_message(
                chat_id=chat.id,
                text="Позиции должны быть положительными.",
                message_thread_id=message_thread_id,
            )
            create_task(delete_later(context, chat, error_message.message_id))
            return

        if pos1 == pos2:
            return  # ничего не делаем

    # Получаем очередь (если ещё не получили)
    if mode == "positions":
        queue = await queue_service.repo.get_queue(chat.id, queue_name)
        if not queue:
            error_message = await context.bot.send_message(
                chat_id=chat.id,
                text=f"Очередь «{queue_name}» не найдена или пуста.",
                message_thread_id=message_thread_id,
            )
            create_task(delete_later(context, chat, error_message.message_id))
            return

        if max(pos1, pos2) >= len(queue):
            error_message = await context.bot.send_message(
                chat_id=chat.id,
                text="Одна из позиций выходит за пределы очереди.",
                message_thread_id=message_thread_id,
            )
            create_task(delete_later(context, chat, error_message.message_id))
            return

        user1, user2 = queue[pos1], queue[pos2]
    else:
        user1, user2 = user_name_1, user_name_2

    # Меняем местами
    queue[pos1], queue[pos2] = queue[pos2], queue[pos1]

    # Сохраняем
    await queue_service.repo.update_queue(chat.id, queue_name, queue)
    ctx.queue_name = queue_name
    # Логируем
    QueueLogger.replaced(chat_title, queue_name, actor, user1, pos1 + 1, user2, pos2 + 1)

    # Обновляем сообщение
    await queue_service.update_queue_message(ctx, query_or_update=update, context=context)


# async def generate_students_list(update: Update, context: ContextTypes.DEFAULT_TYPE, shuffle: bool):
#     chat = update.effective_chat
#     chat_title = chat.title or chat.username or "Личный чат"
#     message_id = update.message.message_id

#     await safe_delete(context, chat, message_id)

#     args = context.args
#     subgroup = None

#     if args and args[-1].upper() in ("A", "B"):
#         subgroup = args.pop(-1).upper()

#     queue_name = " ".join(args) if args else await queue_service.generate_queue_name(chat.id)

#     # Создаём очередь
#     await queue_service.create_queue(chat.id, queue_name, chat_title)

#     # Формируем список студентов
#     students = [(username, group) for username, group in STUDENTS_USERNAMES.values()]
#     if shuffle:
#         random.shuffle(students)

#     added_count = 0
#     for username, group in students:
#         if not subgroup or group == subgroup:
#             await queue_service.add_to_queue(chat.id, queue_name, username, chat_title)
#             added_count += 1

#     if added_count == 0:
#         error_message = await context.bot.send_message("Нет пользователей для добавления.")
#         create_task(delete_later(chat.id, context, chat, error_message.message_id))

#         await queue_service.delete_queue(chat.id, queue_name, chat_title)
#         return

#     await queue_service.send_queue_message(chat, update.message.message_thread_id, context, queue_name)


# @admins_only
# async def generate_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await generate_students_list(update, context, shuffle=True)


# @admins_only
# async def get_list_of_students(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await generate_students_list(update, context, shuffle=False)


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
        create_task(delete_later(context, chat, error.message_id, 10))
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
        create_task(delete_later(context, chat, error.message_id))
        return

    if new_name in queue_names:
        error = await context.bot.send_message(
            chat_id=chat.id,
            text="Очередь с новым именем уже существует.",
            message_thread_id=update.message.message_thread_id,
        )
        create_task(delete_later(context, chat, error.message_id))
        return
    ctx.queue_name = old_name
    await queue_service.rename_queue(ctx, new_name)
    ctx.queue_name = new_name

    # Обновляем сообщение для новой очереди
    await queue_service.update_queue_message(ctx, query_or_update=update, context=context)
