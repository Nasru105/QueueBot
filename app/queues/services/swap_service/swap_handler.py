import logging

from app.queues import queue_service
from app.queues.models import ActionContext
from app.queues.services.swap_service.inline_keyboards import swap_confirmation_keyboard
from app.queues.services.swap_service.swap_service import swap_service
from app.services.logger import QueueLogger
from app.utils.utils import delete_message_later


async def request_swap(context, ctx: ActionContext, members: list[dict], user, target_id: str):
    try:
        requester_id = int(user.id)
        target_id = int(target_id)
    except Exception:
        return

    req_idx, tgt_idx, req_name, tgt_name = None, None, None, None

    for i, user in enumerate(members):
        if int(user.get("user_id") or 0) == requester_id:
            req_idx = i
            req_name = user.get("display_name")
        if int(user.get("user_id") or 0) == target_id:
            tgt_idx = i
            tgt_name = user.get("display_name")

    if req_idx is None or tgt_idx is None or req_idx == tgt_idx:
        return

    REQUEST_TIME = 120
    swap_id = await swap_service.create_swap(
        chat_id=ctx.chat_id,
        queue_id=ctx.queue_id,
        requester_id=requester_id,
        requester_name=req_name,
        target_id=target_id,
        target_name=tgt_name,
        ttl=REQUEST_TIME,
    )

    keyboard = swap_confirmation_keyboard(ctx.queue_id, swap_id)

    await delete_message_later(
        context,
        ctx,
        f"{tgt_name or target_id}, запрос на обмен местом от {req_name}.",
        REQUEST_TIME,
        reply_markup=keyboard,
    )


async def respond_swap(context, ctx: ActionContext, user, swap_id: str, accept: bool):
    swap = await swap_service.get_swap(swap_id)
    if not swap:
        text = "Неизвестный ответ на обмен"
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
        await swap_service.decline_swap(swap_id, user.id)
        await delete_message_later(context, ctx, "Запрос на обмен отклонён.")
        return True

    # accept: validate queue and perform swap
    try:
        queue = await queue_service.repo.get_queue(ctx.chat_id, ctx.queue_id)

        req_id = int(swap.get("requester_id"))
        tgt_id = int(swap.get("target_id"))

        req_idx = next((i for i, it in enumerate(queue) if int(it.get("user_id")) == req_id), None)
        tgt_idx = next((i for i, it in enumerate(queue) if int(it.get("user_id")) == tgt_id), None)

        if req_idx is None or tgt_idx is None:
            await delete_message_later(context, ctx, "Невозможно выполнить обмен — один из пользователей не в очереди.")
            await swap_service.delete_swap(swap_id)
            return

        queue[req_idx], queue[tgt_idx] = queue[tgt_idx], queue[req_idx]
        await queue_service.repo.update_queue(ctx.chat_id, ctx.queue_id, queue["members"])
        await swap_service.accept_swap(swap_id, user.id)
        return True

    except Exception:
        await swap_service.delete_swap(swap_id)
        raise
