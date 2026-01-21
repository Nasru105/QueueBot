import asyncio
import json
import logging
import os
import sys
import time
import weakref
from collections import OrderedDict, deque
from datetime import datetime
from typing import Deque, Dict, Optional

from pythonjsonlogger import json as jsonlogger

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
        ordered["queue"] = log_record.pop("queue", None)
        ordered["chat_title"] = log_record.pop("chat_title", None)
        ordered["actor"] = log_record.pop("actor", None)
        ordered["asctime"] = log_record.pop("asctime", None)
        ordered["level"] = log_record.pop("levelname", None).lower()

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

# === Буферизированный MongoDB Handler ===
try:
    from .mongo_storage import mongo_db

    log_collection = mongo_db.db["log_data"]

    class BufferedMongoHandler(logging.Handler):
        """Буферизированный обработчик для записи логов в MongoDB"""

        # Классовые переменные для управления буфером
        _instances: weakref.WeakSet = weakref.WeakSet()
        _flush_task: Optional[asyncio.Task] = None
        _flush_interval: int = 5  # Секунд между сбросами буфера
        _is_shutting_down = False
        _start_lock = asyncio.Lock()

        def __init__(self, buffer_size: int = 100, flush_interval: int = 5):
            super().__init__()
            self.buffer_size = buffer_size
            self.flush_interval = flush_interval
            self._buffer: Deque[Dict] = deque(maxlen=buffer_size)
            self._lock = asyncio.Lock()

            # Регистрируем этот обработчик
            self.__class__._instances.add(self)

            # Отложенный запуск фоновой задачи (при первом вызове emit)
            self._background_started = False

        def _ensure_background_task(self):
            """Запускает фоновую задачу при необходимости"""
            if not self._background_started and not self.__class__._is_shutting_down:
                # Пытаемся получить работающий event loop
                try:
                    loop = asyncio.get_running_loop()
                    # Если есть работающий loop, запускаем задачу
                    if self.__class__._flush_task is None or self.__class__._flush_task.done():
                        self.__class__._flush_task = loop.create_task(self.__class__._flush_loop())
                    self._background_started = True
                except RuntimeError:
                    # Нет работающего event loop - запустим позже
                    pass

        @classmethod
        async def _flush_loop(cls):
            """Цикл периодического сброса буфера"""
            while not cls._is_shutting_down:
                try:
                    await asyncio.sleep(cls._flush_interval)
                    await cls._flush_all_buffers()
                except asyncio.CancelledError:
                    # Задача была отменена (при shutdown)
                    break
                except Exception:
                    await asyncio.sleep(1)  # Подождать перед повторной попыткой

        @classmethod
        async def _flush_all_buffers(cls):
            """Сбрасывает буферы всех экземпляров обработчика"""
            if not cls._instances:
                return

            for handler in cls._instances:
                await handler._flush_buffer()

        def emit(self, record):
            """Обработка записи лога (синхронная часть)"""
            try:
                # Убедимся, что фоновая задача запущена
                self._ensure_background_task()

                # Форматируем запись лога
                log_entry = self.format(record)

                # Преобразуем JSON строку в dict
                if isinstance(log_entry, str):
                    log_dict = json.loads(log_entry)
                else:
                    log_dict = log_entry

                # Добавляем дополнительные поля
                log_dict["timestamp"] = datetime.now().isoformat()

                # Добавляем в буфер
                self._buffer.append(log_dict)

                # Если буфер заполнен, запускаем немедленный сброс
                if len(self._buffer) >= self.buffer_size:
                    # Пытаемся запустить асинхронную задачу для сброса
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self._flush_buffer())
                    except RuntimeError:
                        # Нет работающего event loop - сохраним для следующего сброса
                        pass

            except Exception as e:
                print(f"BufferedMongoHandler.emit error: {e}", file=sys.stderr)

        async def _flush_buffer(self):
            """Асинхронный сброс буфера в MongoDB"""
            async with self._lock:
                if not self._buffer:
                    return

                try:
                    # Копируем и очищаем буфер
                    logs_to_insert = list(self._buffer)
                    self._buffer.clear()

                    if logs_to_insert:
                        # Вставляем все записи одним запросом
                        await log_collection.insert_many(logs_to_insert)

                except Exception as e:
                    print(f"Failed to flush logs to MongoDB: {e}", file=sys.stderr)
                    # Возвращаем логи обратно в буфер (кроме самых старых, если он переполнен)
                    if len(self._buffer) + len(logs_to_insert) > self.buffer_size:
                        # Оставляем место для новых записей
                        keep_count = self.buffer_size - len(self._buffer)
                        logs_to_insert = logs_to_insert[-keep_count:]

                    # Возвращаем логи в начало буфера
                    self._buffer.extendleft(reversed(logs_to_insert))

        @classmethod
        async def shutdown(cls):
            """Принудительный сброс всех буферов при завершении работы"""
            cls._is_shutting_down = True

            if cls._flush_task:
                cls._flush_task.cancel()
                try:
                    await cls._flush_task
                except asyncio.CancelledError:
                    pass

            # Сбрасываем все буферы
            await cls._flush_all_buffers()

        def close(self):
            """Закрытие обработчика"""
            super().close()
            # Удаляем обработчик из списка
            self.__class__._instances.discard(self)

    # Создаем и настраиваем обработчик
    mongo_handler = BufferedMongoHandler(
        buffer_size=int(os.environ.get("LOG_BUFFER_SIZE", 100)),
        flush_interval=int(os.environ.get("LOG_FLUSH_INTERVAL", 5)),
    )
    mongo_handler.setFormatter(formatter)
    logger.addHandler(mongo_handler)

    print("MongoDB buffered logging initialized successfully")

except ImportError as e:
    print(f"MongoDB logging disabled: {e}")
except Exception as e:
    print(f"Error initializing MongoDB handler: {e}")


class QueueLogger:
    """Класс для логирования действий с очередями"""

    @classmethod
    async def log(
        cls,
        ctx: Optional[ActionContext] = None,
        action: str = "action",
        level: int = logging.INFO,
    ) -> None:
        """
        Асинхронное логирование действия

        Args:
            ctx: Контекст действия (если None, создается новый)
            action: Текст действия
            level: Уровень логирования
        """
        # Создаем контекст только если он не передан
        if ctx is None:
            ctx = ActionContext()

        logger.log(level, action, extra={"chat_title": ctx.chat_title, "queue": ctx.queue_name, "actor": ctx.actor})

    @classmethod
    async def joined(cls, ctx: ActionContext, user_name: str, position: int):
        """Логирование входа пользователя в очередь"""
        await cls.log(ctx, f"join {user_name} ({position})")

    @classmethod
    async def leaved(cls, ctx: ActionContext, user_name: str, position: int):
        """Логирование выхода пользователя из очереди"""
        await cls.log(ctx, f"leave {user_name} ({position})")

    @classmethod
    async def inserted(cls, ctx: ActionContext, user_name: str, position: int):
        """Логирование вставки пользователя в очередь"""
        await cls.log(ctx, f"insert {user_name} ({position})")

    @classmethod
    async def removed(cls, ctx: ActionContext, user_name: str, position: int):
        """Логирование удаления пользователя из очереди"""
        await cls.log(ctx, f"remove {user_name} ({position})")

    @classmethod
    async def replaced(cls, ctx: ActionContext, user_name1: str, pos1: int, user_name2: str, pos2: int):
        """Логирование замены пользователей в очереди"""
        await cls.log(ctx, f"replace {user_name1} ({pos1}) с {user_name2} ({pos2})")


# Дополнительные утилиты для работы с логами
class LogManager:
    """Менеджер для управления логированием"""

    @staticmethod
    async def start():
        """Явный запуск фоновых задач логирования"""
        for handler in logger.handlers:
            if hasattr(handler, "_ensure_background_task"):
                handler._ensure_background_task()

    @staticmethod
    async def flush_all():
        """Принудительный сброс всех буферов логов"""
        for handler in logger.handlers:
            if hasattr(handler, "_flush_buffer"):
                await handler._flush_buffer()

    @staticmethod
    def get_buffer_size() -> int:
        """Получить текущий размер буфера"""
        total = 0
        for handler in logger.handlers:
            if hasattr(handler, "_buffer"):
                total += len(handler._buffer)
        return total

    @staticmethod
    async def shutdown():
        """Корректное завершение работы системы логирования"""
        for handler in logger.handlers:
            if hasattr(handler, "shutdown"):
                await handler.shutdown()


# Экспортируем утилиты
__all__ = ["QueueLogger", "LogManager", "logger"]
