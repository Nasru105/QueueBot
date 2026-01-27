import sys
from functools import partial

from loguru import logger

from app.queues.models import ActionContext

logger.remove()

logger.configure(extra={"chat_title": "-", "queue": "-", "actor": "-"})

logger.add(
    sys.stdout,
    format="<green>{time:DD.MM.YYYY HH:mm:ss}</green> | <level>{level: <8}</level> | {extra[chat_title]} | {extra[queue]} | <cyan>{message}</cyan>",
    level="INFO",
    enqueue=True,
)


async def mongo_sink(mongo_db, message):
    try:
        record = message.record
        extra = record.get("extra", {})
        document = {
            "timestamp": record["time"].strftime("%Y-%m-%d %H:%M:%S"),
            "level": record["level"].name,
            "message": record["message"],
            "chat_title": extra.get("chat_title", "-"),
            "queue": extra.get("queue", "-"),
            "actor": extra.get("actor", "-"),
        }
        await mongo_db.db["log_data"].insert_one(document)
    except Exception as e:
        print(f"Mongo logging error: {e}", file=sys.stderr)


async def setup_logger(mongo_db):
    """Вызывается из bot.py после старта Event Loop"""
    try:
        mongo_sink_with_db = partial(mongo_sink, mongo_db)

        logger.add(mongo_sink_with_db, level="INFO", enqueue=True)

        logger.info("Система логирования инициализирована")
    except Exception as e:
        logger.error(f"Failed to setup Mongo logging: {e}")


class QueueLogger:
    @staticmethod
    def _bind(ctx: ActionContext):
        if not ctx:
            ctx = ActionContext()
        # Перезаписываем дефолтные значения реальными данными
        return logger.bind(
            chat_title=getattr(ctx, "chat_title", "-") or "-",
            queue=getattr(ctx, "queue_name", "-") or "-",
            actor=getattr(ctx, "actor", "-") or "-",
        )

    @classmethod
    async def log(cls, ctx, action, level="INFO"):
        log_func = getattr(cls._bind(ctx), level.lower(), cls._bind(ctx).info)
        log_func(action)

    @classmethod
    async def joined(cls, ctx, user_name, position):
        cls._bind(ctx).info(f"join {user_name} ({position})")

    @classmethod
    async def leaved(cls, ctx, user_name, position):
        cls._bind(ctx).info(f"leave {user_name} ({position})")

    @classmethod
    async def inserted(cls, ctx, user_name, position):
        cls._bind(ctx).info(f"insert {user_name} ({position})")

    @classmethod
    async def removed(cls, ctx, user_name, position):
        cls._bind(ctx).info(f"remove {user_name} ({position})")

    @classmethod
    async def replaced(cls, ctx, u1, p1, u2, p2):
        cls._bind(ctx).info(f"replace {u1} ({p1}) с {u2} ({p2})")


__all__ = ["QueueLogger", "logger", "setup_logger"]
