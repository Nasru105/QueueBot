from typing import Any, Dict, List, Optional

from telegram import User

from app.services.mongo_storage import queue_collection, user_collection
from app.utils.utils import strip_user_full_name

from .errors import (
    ChatNotFoundError,
    QueueAlreadyExistsError,
    QueueNotFoundError,
    UserAlreadyExistsError,
    UserNotFoundError,
)


class QueueRepository:
    """Низкоуровневые операции с MongoDB"""

    async def get_chat(self, chat_id: int) -> Optional[Dict]:
        return await queue_collection.find_one({"chat_id": chat_id})

    async def create_or_get_chat(self, chat_id: int, title: str = None) -> Dict:
        doc = await self.get_chat(chat_id)
        if not doc:
            doc = {"chat_id": chat_id, "queues": [], "chat_title": title}
            await queue_collection.insert_one(doc)
        elif title and doc.get("chat_title") != title:
            await queue_collection.update_one({"chat_id": chat_id}, {"$set": {"chat_title": title}}, upsert=True)

        return doc

    async def update_chat(self, chat_id: int, update: Dict[str, Any]):
        await queue_collection.update_one({"chat_id": chat_id}, {"$set": update}, upsert=True)

    async def get_queue(self, chat_id: int, queue_name: str) -> List[str]:
        doc = await queue_collection.find_one({"chat_id": chat_id})
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")
        for q in doc.get("queues", []):
            if q.get("name") == queue_name:
                return q.get("queue", [])
        raise QueueNotFoundError(f"queue '{queue_name}' not found in chat {chat_id}")

    async def add_to_queue(self, chat_id: int, queue_name: str, user_name: str) -> int:
        doc = await self.get_chat(chat_id)
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queue_idx = None
        for i, q in enumerate(doc.get("queues", [])):
            if q.get("name") == queue_name:
                queue_idx = i
                break

        if queue_idx is None:
            raise QueueNotFoundError(f"queue '{queue_name}' not found in chat {chat_id}")

        queue_list = doc["queues"][queue_idx]["queue"]
        if user_name in queue_list:
            raise UserAlreadyExistsError(f"{user_name} already in queue")

        queue_list.append(user_name)
        await self.update_chat(chat_id, {"queues": doc["queues"]})
        return len(queue_list)

    async def remove_from_queue(self, chat_id: int, queue_name: str, user_name: str) -> Optional[int]:
        doc = await self.get_chat(chat_id)
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queue_idx = None
        for i, q in enumerate(doc.get("queues", [])):
            if q.get("name") == queue_name:
                queue_idx = i
                break

        if queue_idx is None:
            raise QueueNotFoundError(f"queue '{queue_name}' not found in chat {chat_id}")

        queue_list = doc["queues"][queue_idx]["queue"]
        if user_name not in queue_list:
            raise UserNotFoundError(f"user '{user_name}' not found in queue '{queue_name}'")

        position = queue_list.index(user_name) + 1
        queue_list.remove(user_name)
        await self.update_chat(chat_id, {"queues": doc["queues"]})
        return position

    async def create_queue(self, chat_id: int, chat_title: str, queue_name: str):
        doc = await self.create_or_get_chat(chat_id, chat_title)

        # гарантируем, что есть массив queues
        queues: list = doc.setdefault("queues", [])

        # проверяем, нет ли очереди с таким именем
        if any(q.get("name") == queue_name for q in queues):
            raise QueueAlreadyExistsError(f"queue '{queue_name}' already exists in chat {chat_id}")

        # добавляем новую очередь
        new_queue = {"name": queue_name, "queue": [], "last_queue_message_id": None}
        queues.append(new_queue)

        await self.update_chat(chat_id, {"queues": queues})

    async def delete_queue(self, chat_id: int, queue_name: str) -> bool:
        """
        Удаляет очередь по имени.
        Если это была последняя очередь — полностью удаляет документ чата.
        """
        # Получаем документ
        doc = await queue_collection.find_one({"chat_id": chat_id})
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queues = doc.get("queues", [])
        original_count = len(queues)

        # Фильтруем очереди
        new_queues = [q for q in queues if q.get("name") != queue_name]

        if len(new_queues) == original_count:
            # Очередь не найдена
            raise QueueNotFoundError(f"queue '{queue_name}' not found in chat {chat_id}")

        # Очередь найдена и удалена
        if len(new_queues) == 0:
            # Это была последняя очередь → удаляем весь документ
            await queue_collection.delete_one({"chat_id": chat_id})
        else:
            # Остались другие очереди → обновляем массив
            await queue_collection.update_one({"chat_id": chat_id}, {"$set": {"queues": new_queues}})

    async def update_queue(self, chat_id: int, queue_name: str, new_queue: List[str]):
        """
        Обновляет список пользователей в очереди.

        :param chat_id: ID чата
        :param queue_name: Имя очереди
        :param new_queue: Новый список пользователей (List[str])
        """
        doc = await self.get_chat(chat_id)
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queue_idx = None
        for i, q in enumerate(doc.get("queues", [])):
            if q.get("name") == queue_name:
                queue_idx = i
                break

        if queue_idx is not None:
            doc["queues"][queue_idx]["queue"] = new_queue
            await self.update_chat(chat_id, {"queues": doc["queues"]})
        else:
            raise QueueNotFoundError(f"queue '{queue_name}' not found in chat {chat_id}")

    async def get_queue_message_id(self, chat_id: int, queue_name: str) -> Optional[int]:
        """
        Получает message_id очереди по названию.
        """
        doc = await self.get_chat(chat_id)
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        for q in doc.get("queues", []):
            if q.get("name") == queue_name:
                return q.get("last_queue_message_id")
        raise QueueNotFoundError(f"queue '{queue_name}' not found in chat {chat_id}")

    async def set_queue_message_id(self, chat_id: int, queue_name: str, msg_id: int):
        doc = await self.get_chat(chat_id)
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queue_idx = None
        for i, q in enumerate(doc.get("queues", [])):
            if q.get("name") == queue_name:
                queue_idx = i
                break

        if queue_idx is not None:
            doc["queues"][queue_idx]["last_queue_message_id"] = msg_id
            await self.update_chat(chat_id, {"queues": doc["queues"]})
        else:
            raise QueueNotFoundError(f"queue '{queue_name}' not found in chat {chat_id}")

    async def get_all_queues(self, chat_id: int) -> Dict:
        doc = await self.get_chat(chat_id)
        if not doc:
            return {}
        # Convert array format to dict format for compatibility
        queues_dict = {}
        for q in doc.get("queues", []):
            queues_dict[q.get("name")] = {
                "queue": q.get("queue", []),
                "last_queue_message_id": q.get("last_queue_message_id"),
            }
        return queues_dict

    async def get_list_message_id(self, chat_id: int) -> Optional[int]:
        doc = await queue_collection.find_one({"chat_id": chat_id}, {"last_list_message_id": 1})
        return doc.get("last_list_message_id") if doc else None

    async def set_list_message_id(self, chat_id: int, msg_id: int):
        await self.update_chat(chat_id, {"last_list_message_id": msg_id})

    async def clear_list_message_id(self, chat_id: int):
        await self.update_chat(chat_id, {"last_list_message_id": None})

    async def rename_queue(self, chat_id: int, old_name: str, new_name: str):
        doc = await self.get_chat(chat_id)
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queue_idx = None
        for i, q in enumerate(doc.get("queues", [])):
            if q.get("name") == old_name:
                queue_idx = i
                break

        if queue_idx is not None:
            doc["queues"][queue_idx]["name"] = new_name
            await self.update_chat(chat_id, {"queues": doc["queues"]})
        else:
            # Old queue doesn't exist, create new one
            new_queue = {"name": new_name, "queue": [], "last_queue_message_id": None}
            doc["queues"].append(new_queue)
            await self.update_chat(chat_id, {"queues": doc["queues"]})

    async def get_user_display_name(self, user: User) -> str:
        doc_user = await user_collection.find_one({"user_id": user.id})
        if not doc_user:
            # Первый раз видим — создаём
            doc_user = {
                "user_id": user.id,
                "username": user.username,
                "display_names": {"global": strip_user_full_name(user)},
            }
            await user_collection.insert_one(doc_user)
        elif doc_user.get("username", None) != user.username:
            await user_collection.update_one({"user_id": user.id}, {"$set": {"username": user.username}}, upsert=True)

        return doc_user

    async def update_user_display_name(self, user_id: int, display_names: Dict[str, str]):
        await user_collection.update_one({"user_id": user_id}, {"$set": {"display_names": display_names}}, upsert=True)
