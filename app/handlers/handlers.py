# app/handlers/queue_handlers.py
import logging

# import traceback
from asyncio import Lock, create_task, sleep
from uuid import uuid4

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.queues_menu.queue_menu import handle_queue_menu
from app.queues_menu.queues_menu import handle_queues_menu
from app.services.logger import QueueLogger
from app.utils.utils import delete_message_later, has_user, with_ctx

# Локи на чат
chat_locks: dict[int, Lock] = {}
pending_swaps: dict[str, dict] = {}


def get_chat_lock(chat_id: int) -> Lock:
    if chat_id not in chat_locks:
        chat_locks[chat_id] = Lock()
    return chat_locks[chat_id]


@with_ctx
async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    query = update.callback_query
    await query.answer()

    try:
        _, menu_type, queue_id, action = query.data.split("|")
        ctx.queue_id = queue_id
    except ValueError:
        QueueLogger.log(ctx, "Invalid menu callback", level=logging.WARNING)
        return

    if menu_type == "queue":
        await handle_queue_menu(update, context, ctx, action)
    elif menu_type == "queues":
        await handle_queues_menu(update, context, ctx, action)


@with_ctx
async def handle_queue_button(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    """
    Обрабатывает нажатие кнопок для конкретной очереди.
    """
    query = update.callback_query
    await query.answer()

    user = query.from_user

    parts = query.data.split("|")
    if len(parts) not in (3, 4):
        QueueLogger.log(ctx, action="Invalid callback data", level=logging.WARNING)
        return

    _, queue_id, action = parts[0:3]
    target = parts[3] if len(parts) == 4 else None

    queue = await queue_service.repo.get_queue(ctx.chat_id, queue_id)
    queue_name = queue["name"]
    ctx.queue_name = queue_name
    ctx.queue_id = queue_id

    async with get_chat_lock(ctx.chat_id):
        members = queue.get("members", [])
        display_name = await queue_service.get_user_display_name(user, ctx.chat_id)

        if action == "join":
            if not await has_user(members, user.id, display_name):
                await queue_service.join_to_queue(ctx, user)
        elif action == "leave":
            if await has_user(members, user.id, display_name):
                await queue_service.leave_from_queue(ctx, user)
        elif action == "swap" and target:
            await swap(context, ctx, members, user, target)
            await queue_service.message_service.hide_queues_list_message(context, ctx)
            return
        elif action == "swap_accept" and target:
            res = await handle_swap_response(context, ctx, user, target, accept=True)
            if res:
                await context.bot.delete_message(chat_id=ctx.chat_id, message_id=query.message.message_id)
            return
        elif action == "swap_decline" and target:
            res = await handle_swap_response(context, ctx, user, target, accept=False)
            if res:
                await context.bot.delete_message(chat_id=ctx.chat_id, message_id=query.message.message_id)
            return

        await queue_service.update_queue_message(ctx, query, context)


async def swap(context, ctx: ActionContext, members: list[dict], user, target_id: str):
    # swap requested: target may be uid:<id> or an index
    requester_id = int(user.id)

    try:
        target_id = int(target_id)
    except Exception:
        target_id = None

    if not target_id:
        return

    req_idx = None
    tgt_idx = None
    req_name = None
    tgt_name = None

    for i, user in enumerate(members):
        if int(user.get("user_id") or 0) == requester_id:
            req_idx = i
            req_name = user.get("display_name")
        if int(user.get("user_id") or 0) == target_id:
            tgt_idx = i
            tgt_name = user.get("display_name")

    if req_idx is None or tgt_idx is None or req_idx == tgt_idx:
        return

    # create unique swap request id and store minimal state
    swap_id = str(uuid4())
    pending_swaps[swap_id] = {
        "chat_id": ctx.chat_id,
        "queue_id": ctx.queue_id,
        "requester_id": requester_id,
        "target_id": target_id,
    }

    # send confirmation to target in the chat
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text="Да", callback_data=f"queue|{ctx.queue_id}|swap_accept|{swap_id}"),
                InlineKeyboardButton(text="Нет", callback_data=f"queue|{ctx.queue_id}|swap_decline|{swap_id}"),
            ],
        ]
    )

    REQUEST_TIME = 120
    await delete_message_later(
        context,
        ctx,
        f"{tgt_name or target_id}, запрос на обмен местом от {req_name}.",
        REQUEST_TIME,
        reply_markup=keyboard,
    )

    async def _expire_swap(sid: str, delay: int):
        await sleep(delay)
        pending_swaps.pop(sid, None)

    create_task(_expire_swap(swap_id, REQUEST_TIME))


async def handle_swap_response(context, ctx: ActionContext, user, swap_id: str, accept: bool):
    swap = pending_swaps.get(swap_id)
    if not swap:
        text = "Unknown swap response"
        await delete_message_later(context, ctx, text)
        QueueLogger.log(ctx, action=text, level=logging.WARNING)
        return

    # Only the intended target may accept/decline
    if int(user.id) != int(swap.get("target_id")):
        user_name = await queue_service.user_service.get_user_display_name(user, ctx.chat_id)

        text = f"{user_name} не является целью запроса"
        await delete_message_later(context, ctx, text)
        QueueLogger.log(ctx, action=text, level=logging.WARNING)
        return

    if not accept:
        # declined — remove pending and inform
        pending_swaps.pop(swap_id, None)

        await delete_message_later(context, ctx, "Запрос на обмен отклонён.")
        return True

    try:
        queue = await queue_service.repo.get_queue(ctx.chat_id, ctx.queue_id)

        req_id = int(swap.get("requester_id"))
        tgt_id = int(swap.get("target_id"))

        req_idx = next((i for i, it in enumerate(queue) if int(it.get("user_id")) == req_id), None)
        tgt_idx = next((i for i, it in enumerate(queue) if int(it.get("user_id")) == tgt_id), None)

        if req_idx is None or tgt_idx is None:
            await delete_message_later(context, ctx, "Невозможно выполнить обмен — один из пользователей не в очереди.")
            pending_swaps.pop(swap_id, None)
            return

        queue[req_idx], queue[tgt_idx] = queue[tgt_idx], queue[req_idx]
        await queue_service.repo.update_queue_by_name(ctx.chat_id, swap.get("queue_name"), queue)
        await queue_service.update_queue_message(ctx, context=context)
        return True

    finally:
        pending_swaps.pop(swap_id, None)


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
