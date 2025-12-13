# app/handlers/queue_handlers.py
import logging

# import traceback
from asyncio import Lock

from telegram import Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.queues_menu.queue_menu import handle_queue_menu
from app.queues_menu.queues_menu import handle_queues_menu
from app.services.logger import QueueLogger
from app.utils.utils import has_user, with_ctx

# Локи на чат
chat_locks: dict[int, Lock] = {}


def get_chat_lock(chat_id: int) -> Lock:
    if chat_id not in chat_locks:
        chat_locks[chat_id] = Lock()
    return chat_locks[chat_id]


@with_ctx
async def handle_queue_button(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    """
    Обрабатывает нажатие кнопок внутри конкретной очереди (join/leave).
    """
    query = update.callback_query
    await query.answer()

    user = query.from_user
    # Безопасное получение данных из callback
    parts = query.data.split("|")
    if len(parts) not in (3, 4):
        QueueLogger.log(ctx, action="Invalid callback data", level=logging.WARNING)
        return

    _, queue_index_str, action = parts[0:3]
    target = parts[3] if len(parts) == 4 else None

    try:
        queue_index = int(queue_index_str)
    except ValueError:
        QueueLogger.log(ctx, action="Invalid queue index", level=logging.WARNING)
        return

    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    if not (0 <= queue_index < len(queues)):
        QueueLogger.log(ctx, action="Invalid queue index", level=logging.WARNING)
        return

    queue_name = list(queues.keys())[queue_index]
    ctx.queue_name = queue_name

    async with get_chat_lock(ctx.chat_id):
        current_queue = await queue_service.repo.get_queue(ctx.chat_id, queue_name)
        # if there is an entry with display_name only, attach current user id
        try:
            display_name = await queue_service.get_user_display_name(user, ctx.chat_id)
            await queue_service.repo.attach_user_id_by_display_name(ctx.chat_id, queue_name, display_name, user.id)
            current_queue = await queue_service.repo.get_queue(ctx.chat_id, queue_name)
        except Exception:
            pass

        if action == "join":
            if not await has_user(current_queue, user.id, display_name):
                await queue_service.join_to_queue(ctx, user)
            else:
                return
        elif action == "leave":
            print(current_queue, user, display_name)
            if await has_user(current_queue, user.id, display_name):
                print("has_user")
                await queue_service.leave_from_queue(ctx, user)
            else:
                return
        elif action == "swap" and target:
            # swap requested: target may be uid:<id> or an index
            requester_id = user.id
            # find requester index
            req_idx = next((i for i, it in enumerate(current_queue) if it.get("user_id") == requester_id), None)
            if req_idx is None:
                await query.answer("Вы не в очереди")
                return

            # resolve target
            if target.startswith("uid:"):
                try:
                    target_uid = int(target.split(":", 1)[1])
                except Exception:
                    await query.answer("Неверный целевой пользователь")
                    return
                tgt_idx = next((i for i, it in enumerate(current_queue) if it.get("user_id") == target_uid), None)
            else:
                try:
                    tgt_idx = int(target)
                except Exception:
                    tgt_idx = None

            if tgt_idx is None:
                await query.answer("Пользователь больше не в очереди")
                return

            if tgt_idx == req_idx:
                await query.answer("Нельзя поменяться с самим собой")
                return

            # perform swap
            current_queue[req_idx], current_queue[tgt_idx] = current_queue[tgt_idx], current_queue[req_idx]
            await queue_service.repo.update_queue(ctx.chat_id, queue_name, current_queue)
        else:
            return

    await queue_service.update_queue_message(ctx, query_or_update=query, context=context)


@with_ctx
async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    query = update.callback_query
    await query.answer()

    try:
        _, menu_type, queue_index, action = query.data.split("|")
    except ValueError:
        QueueLogger.log(ctx, "Invalid menu callback", level=logging.WARNING)
        return

    if menu_type == "queue":
        await handle_queue_menu(update, context, ctx, int(queue_index), action)
    elif menu_type == "queues":
        await handle_queues_menu(update, context, ctx, queue_index, action)


@with_ctx
async def menu_queue_router(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    query = update.callback_query
    await query.answer()

    try:
        _, menu_type, queue_index, action = query.data.split("|")
    except ValueError:
        QueueLogger.log(ctx, "Invalid menu callback", level=logging.WARNING)
        return

    if menu_type == "swap":
        ...


# async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
#     """
#     Глобальный обработчик ошибок.
#     """
#     chat_title = update.effective_ctx.chat_title if update and update.effective_chat else "Unknown Chat"

#     error_trace = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
#     QueueLogger.log(
#         chat_title=chat_title,
#         action=f"Exception: {error_trace}",
#         level=logging.ERROR,
#     )
