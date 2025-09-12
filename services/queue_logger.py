from datetime import datetime
from typing import Optional

import pytz


class QueueLogger:
    """
    Класс для логирования действий с очередями.
    Позволяет легко менять формат или способ хранения логов.
    """

    @staticmethod
    def _get_time() -> str:
        """Возвращает текущее время в формате HH:MM:SS."""
        moscow_tz = pytz.timezone('Europe/Moscow')
        moscow_time = datetime.now(moscow_tz)
        return moscow_time.strftime("%d.%m.%Y %H:%M:%S")

    @classmethod
    def log(cls, chat_title: Optional[str] = "Unknown Chat", queue_name: str = "Unknown queue", action: str = "action") -> None:
        """
        Логирует действие с очередью.

        :param chat_title: Название чата или username
        :param queue_name: Имя очереди
        :param action: Описание действия
        """

        print(f"{cls._get_time()} | {chat_title} | {queue_name}: {action}", flush=True)

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
    def replaced(cls, chat_title: Optional[str], queue_name: str, user_name1: str, pos1: int, user_name2: str, pos2: int) -> None:
        cls.log(chat_title, queue_name, f"replace {user_name1} ({pos1}) with {user_name2} ({pos2})")
