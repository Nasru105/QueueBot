from telegram import Update
from telegram.ext import ContextTypes

from app.commands.admin import admins_only
from app.queues.models import ActionContext
from app.queues.service import QueueFacadeService
from app.utils.utils import delete_message_later, split_text, with_ctx


@with_ctx()
@admins_only
async def get_logs(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    def format_log(log: dict) -> str:
        lines = []

        chat_title = log.get("chat_title")
        timestamp: str = log.get("timestamp", "-")
        message = log.get("message", "")
        queue = log.get("queue", "-")
        actor = log.get("actor", "-")
        level = log.get("level", "-")

        info_line = []
        if chat_title != "-":
            info_line.append(chat_title)
        if queue != "-":
            info_line.append(queue)

        lines.append(f"🕒 {timestamp} | {level}")
        lines.append(f"🔹 {message}")
        if info_line:
            lines.append("🏷️ " + " | ".join(info_line))
        if actor != "-":
            lines.append(f"👤 {actor}")

        return "\n".join(lines)

    args = context.args
    max_line = 23
    try:
        count = int(args[-1])
    except Exception:
        count = 10

    queue_service: QueueFacadeService = context.bot_data["queue_service"]
    log_collection = queue_service.repo.db["log_data"]
    cursor = log_collection.find().sort("_id", -1).limit(count)
    logs = await cursor.to_list(length=count)

    format_logs = [format_log(log) for log in logs]
    sep = f"\n {'─' * max_line}\n"

    formatted = sep.join(format_logs)
    parts = split_text(formatted, sep)
    for part in parts:
        await delete_message_later(context, ctx, part or "Логи пусты.", 60)


@with_ctx()
@admins_only
async def get_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    queue_service: QueueFacadeService = context.bot_data["queue_service"]
    scheduler = queue_service.auto_cleanup_service.scheduler

    text = "Активные задачи:\n\n"
    for job in scheduler.get_jobs():
        local_time = job.trigger
        text += f"• {job.id}\n {local_time}\n\n"

    parts = split_text(text)
    for part in parts:
        await delete_message_later(context, ctx, part or "jobs пусты.", 60)
