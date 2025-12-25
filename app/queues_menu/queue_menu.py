# import traceback
from telegram import Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.queues_menu.inline_keyboards import queue_swap_keyboard, queues_menu_keyboard
from app.utils.utils import safe_delete


async def handle_queue_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext, action: str):
    queues = await queue_service.repo.get_all_queues(ctx.chat_id)
    queue = queues.get(ctx.queue_id)
    ctx.queue_name = queue["name"]
    query = update.callback_query

    if action == "refresh":
        await queue_service.send_queue_message(ctx, context)
        await queue_service.message_service.hide_queues_list_message(context, ctx)

    elif action == "swap":
        # get queue list by name — support dict keyed by id or by name
        members = queue.get("members", [])
        await query.edit_message_text(
            text=f"{ctx.queue_name}: Отправить запрос на обмен местом c ...",
            reply_markup=await queue_swap_keyboard(members, ctx.queue_id),
        )

    elif action == "delete":
        await queue_service.message_service.hide_queues_list_message(context, ctx)
        last_id = await queue_service.repo.get_queue_message_id(ctx.chat_id, ctx.queue_id)
        if last_id:
            await safe_delete(context.bot, ctx, last_id)

        await queue_service.delete_queue(ctx)

    elif action == "back":
        await query.edit_message_text(text="Список очередей", reply_markup=await queues_menu_keyboard(queues))
