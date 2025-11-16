import json
import logging
import os
import sys
import time
from collections import OrderedDict
from typing import Optional

from pythonjsonlogger import jsonlogger

# Устанавливаем часовой пояс Москва
if os.name != "nt":  # не для Windows
    os.environ["TZ"] = "Europe/Moscow"
    time.tzset()

logger = logging.getLogger("QueueLogger")
logger.setLevel(logging.INFO)


class SafeFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record.setdefault("chat_title", getattr(record, "chat_title", "-"))
        log_record.setdefault("queue", getattr(record, "queue", "-"))

    def process_log_record(self, log_record):
        # стандартная обработка jsonlogger
        log_record = super().process_log_record(log_record)

        # собираем ключи в нужном порядке
        ordered = OrderedDict()
        ordered["asctime"] = log_record.pop("asctime", "")
        ordered["level"] = log_record.pop("levelname", "").lower()
        ordered["chat_title"] = log_record.pop("chat_title", "-")
        ordered["queue"] = log_record.pop("queue", "-")
        ordered["message"] = log_record.pop("message", "")

        # остальные поля — в конце
        for k, v in log_record.items():
            ordered[k] = v

        return ordered

    def to_json(self, record_dict):
        # ensure_ascii=False — важно для кириллицы
        return json.dumps(record_dict, ensure_ascii=False)


formatter = SafeFormatter(
    fmt="%(asctime)s | %(levelname)s | %(chat_title)s | %(queue)s | %(message)s",
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

logger.addHandler(stdout_handler)
logger.addHandler(stderr_handler)

os.makedirs("data/logs", exist_ok=True)
file_handler = logging.FileHandler("data/logs/queue.log", encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


class QueueLogger:
    """
    Класс для логирования действий с очередями.
    Использует стандартную библиотеку logging.
    """

    @classmethod
    def log(
        cls,
        chat_title: Optional[str] = "Unknown Chat",
        queue_name: str = "Unknown queue",
        action: str = "action",
        level: int = logging.INFO,
    ) -> None:
        logger.log(level, action, extra={"chat_title": chat_title, "queue": queue_name})

    @classmethod
    def joined(cls, chat_title: Optional[str], queue_name: str, user_name: str, position: int) -> None:
        cls.log(chat_title, queue_name, f"join {user_name} ({position})")

    @classmethod
    def leaved(cls, chat_title: Optional[str], queue_name: str, user_name: str, position: int) -> None:
        cls.log(chat_title, queue_name, f"leave {user_name} ({position})")

    @classmethod
    def inserted(cls, chat_title: Optional[str], queue_name: str, user_name: str, position: int) -> None:
        cls.log(chat_title, queue_name, f"insert {user_name} ({position})")

    @classmethod
    def removed(cls, chat_title: Optional[str], queue_name: str, user_name: str, position: int) -> None:
        cls.log(chat_title, queue_name, f"remove {user_name} ({position})")

    @classmethod
    def replaced(
        cls,
        chat_title: Optional[str],
        queue_name: str,
        user_name1: str,
        pos1: int,
        user_name2: str,
        pos2: int,
    ) -> None:
        cls.log(
            chat_title,
            queue_name,
            f"replace {user_name1} ({pos1}) с {user_name2} ({pos2})",
        )
