import logging
import os
import sys
import time
from typing import Optional


# Устанавливаем часовой пояс Москва
if os.name != "nt":  # не для Windows
    os.environ["TZ"] = "Europe/Moscow"
    time.tzset()

logger = logging.getLogger("QueueLogger")
logger.setLevel(logging.INFO)
# Формат логов
formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)s | %(message)s", datefmt="%d.%m.%Y %H:%M:%S"
)

# Обработчик для консоли (для Docker/Promtail)
console_handler = logging.StreamHandler(sys.stdout)  # Явно указываем stdout
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

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
        """
        Логирует действие с очередью на указанном уровне.

        :param chat_title: Название чата или username
        :param queue_name: Имя очереди
        :param action: Текст действия
        :param level: Уровень логирования (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        logger.log(level, f"{chat_title} | {queue_name}: {action}")

    @classmethod
    def joined(
        cls, chat_title: Optional[str], queue_name: str, user_name: str, position: int
    ) -> None:
        cls.log(chat_title, queue_name, f"join {user_name} ({position})")

    @classmethod
    def leaved(
        cls, chat_title: Optional[str], queue_name: str, user_name: str, position: int
    ) -> None:
        cls.log(chat_title, queue_name, f"leave {user_name} ({position})")

    @classmethod
    def inserted(
        cls, chat_title: Optional[str], queue_name: str, user_name: str, position: int
    ) -> None:
        cls.log(chat_title, queue_name, f"insert {user_name} ({position})")

    @classmethod
    def removed(
        cls, chat_title: Optional[str], queue_name: str, user_name: str, position: int
    ) -> None:
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
            f"replace {user_name1} ({pos1}) with {user_name2} ({pos2})",
        )
