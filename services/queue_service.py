import json

from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from services.storage import load_data, save_data
from utils.InlineKeyboards import queue_keyboard
from utils.utils import safe_delete, get_time


class QueueManager:
    def __init__(self):
        # Загружаем данные и конвертируем ключи к int
        self.data = load_data() or {}
        # Приводим ключи чатов к int, инициализируем ключ "queues" если нет
        self.data = {
            int(chat): {
                "queues": {str(q): val for q, val in chat_data.get("queues", {}).items()},
                "last_queues_message_id": chat_data.get("last_queues_message_id")
            }
            for chat, chat_data in self.data.items()
        }
        # print(json.dumps(self.data, ensure_ascii=False, indent=4))

    async def save(self):
        save_data(self.data)

    async def create_queue(self, chat, queue_name):
        if chat.id not in self.data:
            self.data[chat.id] = {"queues": {}, "last_queues_message_id": None}

        if queue_name not in self.data[chat.id]["queues"]:
            self.data[chat.id]["queues"][queue_name] = {"queue": [], "last_queue_message_id": None}

        await self.save()
        print(f"{get_time()}|{chat.title if chat.title else chat.username}: create queue '{queue_name}'", flush=True)

    async def delete_queue(self, chat, queue_name):
        if chat.id in self.data and queue_name in self.data[chat.id]["queues"]:
            del self.data[chat.id]["queues"][queue_name]

            # Если после удаления очередь пуста, можно очистить пустой чат (опционально)
            if not self.data[chat.id]["queues"]:
                del self.data[chat.id]

            await self.save()
            print(f"{get_time()}|{chat.title if chat.title else chat.username}: delete queue '{queue_name}'", flush=True)
        else:
            print(f"{get_time()}|{chat.title if chat.title else chat.username}: queue '{queue_name}' not found in chat {chat.id}", flush=True)

    async def add_to_queue(self, chat, queue_name, user_name):
        if chat.id not in self.data:
            self.data[chat.id] = {"queues": {}, "last_queues_message_id": None}

        if queue_name not in self.data[chat.id]["queues"]:
            self.data[chat.id]["queues"][queue_name] = {"queue": [], "last_queue_message_id": None}

        if user_name not in self.data[chat.id]["queues"][queue_name]["queue"]:
            self.data[chat.id]["queues"][queue_name]["queue"].append(user_name)
            await self.save()
            print(f"{get_time()}|{chat.title if chat.title else chat.username}|{queue_name}: join {user_name} ({len(self.data[chat.id]['queues'][queue_name]['queue'])})", flush=True)

    async def remove_from_queue(self, chat, queue_name, user_name):
        if chat.id in self.data and queue_name in self.data[chat.id]["queues"]:
            queue = self.data[chat.id]["queues"][queue_name]["queue"]
            if user_name in queue:
                position = queue.index(user_name)
                queue.remove(user_name)
                await self.save()
                print(f"{get_time()}|{chat.title if chat.title else chat.username}|{queue_name}: leave {user_name} ({position + 1})", flush=True)

    async def get_queue(self, chat_id, queue_name):
        return self.data.get(chat_id, {}).get("queues", {}).get(queue_name, {}).get("queue", [])

    async def get_last_queue_message_id(self, chat_id, queue_name):
        return self.data.get(chat_id, {}).get("queues", {}).get(queue_name, {}).get("last_queue_message_id")

    async def set_last_queue_message_id(self, chat_id: int, queue_name: str, msg_id: int):
        if chat_id not in self.data:
            self.data[chat_id] = {"queues": {}, "last_queues_message_id": None}
        if queue_name not in self.data[chat_id]["queues"]:
            self.data[chat_id]["queues"][queue_name] = {"queue": [], "last_queue_message_id": None}
        self.data[chat_id]["queues"][queue_name]["last_queue_message_id"] = msg_id
        await self.save()

    async def get_queue_text(self, chat_id, queue_name):
        q = await self.get_queue(chat_id, queue_name)
        escaped_name = escape_markdown(queue_name, version=2)
        text = f"*`{escaped_name}`*\n\n"

        if not q:
            text += "Очередь пуста\\."
        else:
            text += "\n".join(f"{i + 1}\\. {u}" for i, u in enumerate(q))

        return text

    async def send_queue_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, queue_name="default"):
        chat = update.effective_chat
        message_thread_id = update.message.message_thread_id if update.message else None

        last_id = await self.get_last_queue_message_id(chat.id, queue_name)
        if last_id:
            await safe_delete(context, chat, last_id)

        sent = await context.bot.send_message(
            chat_id=chat.id,
            text=await self.get_queue_text(chat.id, queue_name),
            parse_mode="MarkdownV2",
            reply_markup=queue_keyboard(queue_name),
            message_thread_id=message_thread_id
        )

        await self.set_last_queue_message_id(chat.id, queue_name, sent.message_id)

    async def get_count_queues(self, chat_id):
        queues = await self.get_queues(chat_id)
        return len(queues)

    async def get_queues(self, chat_id):
        if chat_id not in self.data:
            self.data[chat_id] = {"queues": {}, "last_queues_message_id": None}
        return self.data[chat_id]["queues"]

    async def get_last_queues_message_id(self, chat_id: int) -> int | None:
        return self.data.get(chat_id, {}).get("last_queues_message_id")

    async def set_last_queues_message_id(self, chat_id: int, msg_id: int):
        if chat_id not in self.data:
            self.data[chat_id] = {"queues": {}, "last_queues_message_id": None}
        self.data[chat_id]["last_queues_message_id"] = msg_id
        await self.save()


# Инициализируем менеджер
queue_manager = QueueManager()
