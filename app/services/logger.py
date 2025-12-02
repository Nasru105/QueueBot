import asyncio
import json
import logging
import os
import sys
import time
from collections import OrderedDict

from pythonjsonlogger import jsonlogger

from app.queues.models import ActionContext

# Устанавливаем часовой пояс Москва
if os.name != "nt":  # не для Windows
    os.environ["TZ"] = "Europe/Moscow"
    time.tzset()

logger = logging.getLogger("QueueLogger")
logger.setLevel(logging.INFO)

# === ПАПКА ДЛЯ ЛОГОВ (важно для Loki/Promtail) ===
LOG_DIR = os.environ.get("LOG_DIR", "/var/log/queuebot")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "queue.log")


class SafeFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record.setdefault("chat_title", getattr(record, "chat_title", "-"))
        log_record.setdefault("queue", getattr(record, "queue", "-"))
        log_record.setdefault("actor", getattr(record, "actor", "-"))

    def process_log_record(self, log_record):
        log_record = super().process_log_record(log_record)

        ordered = OrderedDict()
        ordered["message"] = log_record.pop("message", None)
        ordered["asctime"] = log_record.pop("asctime", None)
        ordered["level"] = log_record.pop("levelname", None).lower()
        ordered["chat_title"] = log_record.pop("chat_title", None)
        ordered["queue"] = log_record.pop("queue", None)
        ordered["actor"] = log_record.pop("actor", None)

        for k, v in log_record.items():
            ordered[k] = v

        return ordered

    def to_json(self, record_dict):
        return json.dumps(record_dict, ensure_ascii=False)


formatter = SafeFormatter(
    fmt="%(asctime)s | %(levelname)s | %(chat_title)s | %(queue)s | %(message)s | %(actor)s",
    datefmt="%d.%m.%Y %H:%M:%S",
    json_ensure_ascii=False,
)


class ErrorFilter(logging.Filter):
    def filter(self, record):
        return record.levelno >= logging.ERROR


class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno < logging.ERROR


stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.addFilter(InfoFilter())
stdout_handler.setFormatter(formatter)

stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.addFilter(ErrorFilter())
stderr_handler.setFormatter(formatter)

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(formatter)

logger.addHandler(stdout_handler)
logger.addHandler(stderr_handler)
logger.addHandler(file_handler)

# === MongoDB Handler ===
try:
    from .mongo_storage import log_collection

    class MongoHandler(logging.Handler):
        def emit(self, record):
            try:
                # Форматируем запись лога как dict
                log_entry = self.format(record)

                # Преобразуем JSON строку в dict
                if isinstance(log_entry, str):
                    log_dict = json.loads(log_entry)
                else:
                    log_dict = log_entry

                # Создаем новое событие для асинхронной вставки
                async def insert_log():
                    try:
                        await log_collection.insert_one(log_dict)
                    except Exception as e:
                        print(f"Error inserting log to MongoDB: {e}")

                # Запускаем асинхронную задачу
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Если цикл уже запущен, создаем задачу
                        asyncio.create_task(insert_log())
                    else:
                        # Если цикл не запущен, запускаем его
                        loop.run_until_complete(insert_log())
                except RuntimeError:
                    # Если нет event loop, создаем новый
                    asyncio.run(insert_log())

            except Exception as e:
                # Логируем ошибку, но не прерываем выполнение
                print(f"MongoDB logging error: {e}")

    mongo_handler = MongoHandler()
    mongo_handler.setFormatter(formatter)
    logger.addHandler(mongo_handler)

except ImportError as e:
    print(f"MongoDB logging disabled: {e}")
except Exception as e:
    print(f"Error initializing MongoDB handler: {e}")


class QueueLogger:
    @classmethod
    def log(cls, ctx: ActionContext = ActionContext(), action: str = "action", level: int = logging.INFO) -> None:
        logger.log(level, action, extra={"chat_title": ctx.chat_title, "queue": ctx.queue_name, "actor": ctx.actor})

    @classmethod
    def joined(cls, ctx: ActionContext, user_name, position):
        cls.log(ctx, f"join {user_name} ({position})")

    @classmethod
    def leaved(cls, ctx: ActionContext, user_name, position):
        cls.log(ctx, f"leave {user_name} ({position})")

    @classmethod
    def inserted(cls, ctx: ActionContext, user_name, position):
        cls.log(ctx, f"insert {user_name} ({position})")

    @classmethod
    def removed(cls, ctx: ActionContext, user_name, position):
        cls.log(ctx, f"remove {user_name} ({position})")

    @classmethod
    def replaced(cls, ctx: ActionContext, user_name1, pos1, user_name2, pos2):
        cls.log(ctx, f"replace {user_name1} ({pos1}) с {user_name2} ({pos2})")
