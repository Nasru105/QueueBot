# import traceback
from telegram import Update
from telegram.ext import ContextTypes

from app.queues import queue_service
from app.queues.models import ActionContext
from app.queues.services.swap_service.inline_keyboards import queue_swap_keyboard
from app.queues_menu.inline_keyboards import queues_menu_keyboard
from app.utils.utils import delete_message_later, safe_delete


async def handle_queue_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext, action: str):
    query = update.callback_query
    queue = await queue_service.repo.get_queue(ctx.chat_id, ctx.queue_id)
    if not queue:
        await delete_message_later(context, ctx, "Невозможно выполнить действие.")
        return
    ctx.queue_name = queue["name"]

    if action == "refresh":
        await queue_service.send_queue_message(ctx, context)

    elif action == "swap":
        members = queue.get("members", [])
        await query.edit_message_text(
            text=f"{ctx.queue_name}: Отправить запрос на обмен местом c ...",
            reply_markup=await queue_swap_keyboard(members, ctx.queue_id),
        )
        return

    elif action == "delete":
        last_id = await queue_service.repo.get_queue_message_id(ctx.chat_id, ctx.queue_id)
        if last_id:
            await safe_delete(context.bot, ctx, last_id)

        await queue_service.delete_queue(ctx)

    elif action == "back":
        queues = await queue_service.repo.get_all_queues(ctx.chat_id)
        await query.edit_message_text(text="Список очередей", reply_markup=await queues_menu_keyboard(queues))
        return

    await queue_service.message_service.hide_queues_list_message(context, ctx, query.message.message_id)
