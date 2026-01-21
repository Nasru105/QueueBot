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

    args = context.args
    try:
        count = int(args[-1])
    except Exception:
        count = 10

    log_collection = mongo_db.db["log_data"]
    cursor = log_collection.find().sort("_id", -1).limit(count)
    logs = await cursor.to_list(length=count)

    formatted = "\n──────────────\n".join(format_log(log) for log in logs)

    # 🔥 Разбиваем на части
    parts = split_text(formatted)

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
