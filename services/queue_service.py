import json

from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from services.queue_logger import QueueLogger
from services.storage import load_data, save_data
from utils.InlineKeyboards import queue_keyboard
from utils.utils import safe_delete


class QueueManager:
    def __init__(self):
        # Загружаем сохранённые данные из файла (dict) или создаём пустой словарь
        self.data = load_data() or {}

        # Приводим ключи (ID чатов) к типу int и убеждаемся, что у каждого чата
        # есть структура с ключом "queues" и "last_queues_message_id"
        self.data = {
            int(chat): {
                "queues": {str(q): val for q, val in chat_data.get("queues", {}).items()},
                "last_queues_message_id": chat_data.get("last_queues_message_id")
            }
            for chat, chat_data in self.data.items()
        }

    async def save(self):
        """Сохраняет текущее состояние self.data в JSON-файл"""
        save_data(self.data)

    async def create_queue(self, chat, queue_name):
        """Создаёт новую очередь с указанным названием"""
        # Инициализация структуры для чата, если её ещё нет
        if chat.id not in self.data:
            self.data[chat.id] = {"queues": {}, "last_queues_message_id": None}

        # Добавляем очередь, если её ещё нет
        if queue_name not in self.data[chat.id]["queues"]:
            self.data[chat.id]["queues"][queue_name] = {"queue": [], "last_queue_message_id": None}

        await self.save()
        QueueLogger.log(chat.title or chat.username, queue_name, "create queue")

    async def delete_queue(self, chat, queue_name):
        """Удаляет очередь по имени"""
        if chat.id in self.data and queue_name in self.data[chat.id]["queues"]:
            del self.data[chat.id]["queues"][queue_name]

            # Если в чате больше нет очередей, можно удалить сам чат из базы
            if not self.data[chat.id]["queues"]:
                del self.data[chat.id]

            await self.save()
            QueueLogger.log(chat.title or chat.username, queue_name, "delete queue")

        else:
            QueueLogger.log(chat.title or chat.username, queue_name, "queue not found in chat")

    async def add_to_queue(self, chat, queue_name, user_name):
        """Добавляет пользователя в очередь"""
        if chat.id not in self.data:
            self.data[chat.id] = {"queues": {}, "last_queues_message_id": None}

        if queue_name not in self.data[chat.id]["queues"]:
            self.data[chat.id]["queues"][queue_name] = {"queue": [], "last_queue_message_id": None}

        queue = self.data[chat.id]["queues"][queue_name]["queue"]
        if user_name not in queue:
            queue.append(user_name)
            await self.save()
            position = len(queue)
            QueueLogger.joined(chat.title or chat.username, queue_name, user_name, position)

    async def remove_from_queue(self, chat, queue_name: str, user_name: str):
        """Удаляет пользователя из очереди"""
        if chat.id in self.data and queue_name in self.data[chat.id]["queues"]:
            queue = self.data[chat.id]["queues"][queue_name]["queue"]
            if user_name in queue:
                position = queue.index(user_name)  # Запоминаем позицию перед удалением
                queue.remove(user_name)
                await self.save()
                QueueLogger.leaved(chat.title or chat.username, queue_name, user_name, position + 1)


    async def get_queue(self, chat_id: int, queue_name: str ):
        """Возвращает список пользователей в очереди"""
        return self.data.get(chat_id, {}).get("queues", {}).get(queue_name, {}).get("queue", [])

    async def get_last_queue_message_id(self, chat_id: int, queue_name: str, ):
        """Возвращает ID последнего сообщения с очередью"""
        return self.data.get(chat_id, {}).get("queues", {}).get(queue_name, {}).get("last_queue_message_id")

    async def set_last_queue_message_id(self, chat_id: int, queue_name: str, msg_id: int):
        """Сохраняет ID последнего сообщения с очередью"""
        if chat_id not in self.data:
            self.data[chat_id] = {"queues": {}, "last_queues_message_id": None}
        if queue_name not in self.data[chat_id]["queues"]:
            self.data[chat_id]["queues"][queue_name] = {"queue": [], "last_queue_message_id": None}
        self.data[chat_id]["queues"][queue_name]["last_queue_message_id"] = msg_id
        await self.save()

    async def get_queue_text(self, chat_id: int, queue_name: str):
        """Формирует текст очереди для отправки в чат"""
        q = await self.get_queue(chat_id, queue_name)
        escaped_name = escape_markdown(queue_name, version=2)
        text = f"*`{escaped_name}`*\n\n"

        if not q:
            text += "Очередь пуста\\."
        else:
            text += "\n".join(f"{i + 1}\\. {u}" for i, u in enumerate(q))

        return text

    async def get_queue_name(self, chat_id: int):
        count_queue = 0
        queue_name = f"Очередь {count_queue + 1}"
        while await self.get_queue(chat_id, queue_name):
            count_queue += 1
            queue_name = f"Очередь {count_queue}"
        return queue_name

    async def send_queue_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, queue_name):
        """Отправляет или обновляет сообщение с очередью"""
        chat = update.effective_chat
        message_thread_id = update.message.message_thread_id if update.message else None

        # Удаляем предыдущее сообщение с этой очередью, если есть
        last_id = await self.get_last_queue_message_id(chat.id, queue_name)
        if last_id:
            await safe_delete(context, chat, last_id)

        # Получаем индекс очереди, чтобы правильно построить клавиатуру
        queues = await queue_manager.get_queues(chat.id)
        queue_index = list(queues).index(queue_name)

        # Отправляем сообщение
        sent = await context.bot.send_message(
            chat_id=chat.id,
            text=await self.get_queue_text(chat.id, queue_name),
            parse_mode="MarkdownV2",
            reply_markup=queue_keyboard(queue_index),
            message_thread_id=message_thread_id
        )

        # Запоминаем ID отправленного сообщения
        await self.set_last_queue_message_id(chat.id, queue_name, sent.message_id)

    async def get_count_queues(self, chat_id: int):
        """Возвращает количество очередей в чате"""
        queues = await self.get_queues(chat_id)
        return len(queues)

    async def get_queues(self, chat_id):
        """Возвращает все очереди чата"""
        if chat_id not in self.data:
            self.data[chat_id] = {"queues": {}, "last_queues_message_id": None}
        return self.data[chat_id]["queues"]

    async def get_last_queues_message_id(self, chat_id: int) -> int | None:
        """Возвращает ID последнего сообщения со списком всех очередей"""
        return self.data.get(chat_id, {}).get("last_queues_message_id")

    async def set_last_queues_message_id(self, chat_id: int, msg_id: int):
        """Сохраняет ID последнего сообщения со списком всех очередей"""
        if chat_id not in self.data:
            self.data[chat_id] = {"queues": {}, "last_queues_message_id": None}
        self.data[chat_id]["last_queues_message_id"] = msg_id
        await self.save()

    async def rename_queue(self, chat, old_queue_name: str, new_queue_name: str):
        """Переименовывает очередь в чате"""
        if chat.id not in self.data:
            self.data[chat.id] = {"queues": {}, "last_queues_message_id": None}

        queues = self.data[chat.id]["queues"]

        # Если старая очередь существует – переносим её под новым именем
        if old_queue_name in queues:
            queues[new_queue_name] = queues.pop(old_queue_name)
            QueueLogger.log(chat.title or chat.username, f"{old_queue_name} → {new_queue_name}", "rename queue")
        else:
            # Если не существует — просто создаём пустую с новым именем
            queues[new_queue_name] = {"queue": [], "last_queue_message_id": None}
            QueueLogger.log(chat.title or chat.username, new_queue_name, "create (rename fallback)")

        await self.save()


# Глобальный экземпляр менеджера
queue_manager = QueueManager()
