from datetime import timedelta, timezone

from telegram import Update
from telegram.ext import ContextTypes

from app.commands.admin import admins_only
from app.queues.models import ActionContext
from app.services.mongo_storage import mongo_db
from app.utils.utils import delete_message_later, split_text, with_ctx


@with_ctx
@admins_only
async def get_logs(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    max_line = 0

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

        lines.append(f"🕒 {timestamp.strftime('%Y-%m-%d %H:%M:%S')} | {level}")
        lines.append(f"🔹 {message}")
        if info_line:
            lines.append("🏷️ " + " | ".join(info_line))
        if actor != "-":
            lines.append(f"👤 {actor}")

        nonlocal max_line
        max_line = max([len(line) for line in lines])

        return "\n".join(lines)

    args = context.args
    try:
        count = int(args[-1])
    except Exception:
        count = 10

    log_collection = mongo_db.db["log_data"]
    cursor = log_collection.find().sort("_id", -1).limit(count)
    logs = await cursor.to_list(length=count)

    format_logs = [format_log(log) for log in logs]
    sep = f"\n {'─' * max_line}\n"

    formatted = sep.join(format_logs)

    # 🔥 Разбиваем на части
    parts = split_text(formatted, sep)

    # 📨 Отправляем по очереди
    for part in parts:
        await delete_message_later(context, ctx, part or "Логи пусты.", 60)


@with_ctx
@admins_only
async def get_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE, ctx: ActionContext):
    jobs = context.job_queue.jobs()

    MSK = timezone(timedelta(hours=3))

    text = "Активные задачи:\n\n"
    for job in jobs:
        local_time = job.next_t.astimezone(MSK).strftime("%d.%m.%Y %H:%M:%S")
        text += f"• {job.name}\n  next MSK: {local_time}\n\n"

    # 🔥 Разбиваем на части
    parts = split_text(text)

    # 📨 Отправляем по очереди
    for part in parts:
        await delete_message_later(context, ctx, part or "jobs пусты.", 60)
