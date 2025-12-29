from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from telegram import User

from app.services.mongo_storage import queue_collection, user_collection
from app.utils.utils import get_now, strip_user_full_name

from .errors import (
    ChatNotFoundError,
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
            # store queues as a dict keyed by queue_id for faster lookup and atomic updates
            doc = {"chat_id": chat_id, "queues": {}, "chat_title": title, "last_list_message_id": None}
            await queue_collection.insert_one(doc)
        elif title and doc.get("chat_title") != title:
            await queue_collection.update_one({"chat_id": chat_id}, {"$set": {"chat_title": title}}, upsert=True)

        return doc

    async def update_chat(self, chat_id: int, update: Dict[str, Any]):
        await queue_collection.update_one({"chat_id": chat_id}, {"$set": update}, upsert=True)

    async def get_queue(self, chat_id: int, queue_id: int) -> dict[str, Any]:
        doc = await queue_collection.find_one({"chat_id": chat_id})
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")
        queues = doc.get("queues", {})
        if queue_id in queues:
            return queues[queue_id]
        raise QueueNotFoundError(f"queue ({queue_id}) not found in chat {chat_id}")

    async def get_queue_by_name(self, chat_id: int, queue_name: str) -> List[dict]:
        doc = await queue_collection.find_one({"chat_id": chat_id})
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")
        queues = doc.get("queues", {})
        for queue in queues.values():
            if queue.get("name") == queue_name:
                return queue
        raise QueueNotFoundError(f"queue '{queue_name}' not found in chat {chat_id}")

    async def add_to_queue(self, chat_id: int, queue_id: str, user_id: int, display_name: str) -> int:
        doc = await self.get_chat(chat_id)
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queues = doc.get("queues", {})
        queue = queues[queue_id].setdefault("members", [])

        # queue_list now stores dicts: {"user_id": int, "display_name": str}
        if any(u.get("user_id") == user_id for u in queue):
            raise UserAlreadyExistsError(f"user {user_id} already in queue")

        queue.append({"user_id": user_id, "display_name": display_name})
        queues[queue_id]["last_modified"] = await get_now()
        await self.update_chat(chat_id, {"queues": queues})
        return len(queue)

    async def remove_from_queue(self, chat_id: int, queue_id: str, user_id: int) -> Optional[int]:
        doc = await self.get_chat(chat_id)
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queues = doc.get("queues", {})
        members = queues[queue_id].get("members", [])
        # find by user_id
        idx = next((i for i, u in enumerate(members) if u.get("user_id") == user_id), None)
        if idx is None:
            raise UserNotFoundError(f"user id '{user_id}' not found in queue '{queue_id}'")

        position = idx + 1
        members.pop(idx)
        queues[queue_id]["last_modified"] = await get_now()
        await self.update_chat(chat_id, {"queues": queues})
        return position

    async def create_queue(self, chat_id: int, chat_title: str, queue_name: str) -> str:
        doc = await self.create_or_get_chat(chat_id, chat_title)

        # гарантируем, что queues — словарь
        queues: dict = doc.setdefault("queues", {})

        # проверка по имени
        for queue in queues.values():
            if queue.get("name") == queue_name:
                return queue.get("id")

        queue_id = uuid4().hex[:8]

        new_queue = {
            "id": queue_id,
            "name": queue_name,
            "members": [],
            "last_queue_message_id": None,
            "last_modified": await get_now(),
        }

        # атомарное обновление
        await self.update_chat(chat_id, {f"queues.{queue_id}": new_queue})
        return queue_id

    async def delete_queue(self, chat_id: int, queue_id: str) -> bool:
        """
        Удаляет очередь.
        Если это была последняя очередь — полностью удаляет документ чата.
        """
        # Получаем документ
        doc = await queue_collection.find_one({"chat_id": chat_id})
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queues = doc.get("queues", {}) or {}

        # Удаляем очередь
        del queues[queue_id]

        if not queues:
            # Это была последняя очередь → удаляем весь документ
            await queue_collection.delete_one({"chat_id": chat_id})
        else:
            # Остались другие очереди → обновляем словарь
            await self.update_chat(chat_id, {"queues": queues})

    async def update_queue_members(self, chat_id: int, queue_id: str, new_members: List[dict]):
        """
        Обновляет список пользователей в очереди.
        """
        doc = await self.get_chat(chat_id)
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queues = doc.get("queues", {})

        if queue_id in queues:
            # expect new_queue to be list of dicts
            queues[queue_id]["members"] = new_members
            queues[queue_id]["last_modified"] = await get_now()
            await self.update_chat(chat_id, {"queues": queues})
        else:
            raise QueueNotFoundError(f"queue '{queue_id}' not found in chat {chat_id}")

    async def get_last_modified_time(self, chat_id: int, queue_id: str) -> Optional[datetime]:
        """Возвращает datetime или None. Поддерживает старый строковый формат."""
        doc = await self.get_chat(chat_id)
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queues = doc.get("queues", {})
        queue = queues.get(queue_id)
        if not queue:
            raise QueueNotFoundError(f"queue ({queue_id}) not found in chat {chat_id}")

        return queue.get("last_modified")

    async def get_queue_message_id(self, chat_id: int, queue_id: str) -> Optional[int]:
        """
        Получает message_id очереди.
        """
        doc = await self.get_chat(chat_id)
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queues = doc.get("queues", {})
        queue = queues.get(queue_id)
        if not queue:
            raise QueueNotFoundError(
                f"Failed to get last_queue_message_id: queue ({queue_id}) not found in chat {chat_id}"
            )
        return queue.get("last_queue_message_id")

    async def set_queue_message_id(self, chat_id: int, queue_id: str, msg_id: int):
        doc = await self.get_chat(chat_id)
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queues = doc.get("queues", {})

        if queue_id in queues:
            queues[queue_id]["last_queue_message_id"] = msg_id
            await self.update_chat(chat_id, {"queues": queues})
        else:
            raise QueueNotFoundError(
                f"Failed to set last_queue_message_id: queue ({queue_id}) not found in chat {chat_id}"
            )

    async def get_all_queues(self, chat_id: int) -> Dict[str, Dict[str, Any]]:
        doc = await self.get_chat(chat_id)
        if not doc:
            return {}
        return doc.get("queues", {})

    async def get_list_message_id(self, chat_id: int) -> Optional[int]:
        doc = await queue_collection.find_one({"chat_id": chat_id}, {"last_list_message_id": 1})
        return doc.get("last_list_message_id") if doc else None

    async def set_list_message_id(self, chat_id: int, msg_id: int):
        await self.update_chat(chat_id, {"last_list_message_id": msg_id})

    async def clear_list_message_id(self, chat_id: int):
        await self.update_chat(chat_id, {"last_list_message_id": None})

    async def get_queue_description(self, chat_id: int, queue_id: int) -> Optional[int]:
        queue = await self.get_queue(chat_id, queue_id)
        if not queue:
            raise QueueNotFoundError(f"Failed to get description: queue ({queue_id}) not found in chat {chat_id}")
        return queue["description"]

    async def set_queue_description(self, chat_id: int, queue_id: int, description: str = None) -> Optional[int]:
        queue = await self.get_queue(chat_id, queue_id)
        if queue:
            await self.update_chat(chat_id, {f"queues.{queue_id}.description": description})
        else:
            raise QueueNotFoundError(f"Failed to get description: queue ({queue_id}) not found in chat {chat_id}")

    async def clear_queue_description(self, chat_id: int, queue_id: int):
        await self.set_queue_description(chat_id, queue_id)

    async def get_queue_expiration(self, chat_id: int, queue_id: str) -> Optional[datetime]:
        """Возвращает datetime expiration или None. Поддерживает старый строковый формат."""
        queue = await self.get_queue(chat_id, queue_id)
        return queue.get("expiration")

    async def set_queue_expiration(self, chat_id: int, queue_id: str, expiration):
        """Устанавливает время автоудаления очереди.

        Параметр `expiration` может быть `datetime` или строкой в старом формате — метод сохранит datetime в БД.
        """
        doc = await self.get_chat(chat_id)
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queues = doc.get("queues", {})
        if queue_id in queues:
            queues[queue_id]["expiration"] = expiration
            await self.update_chat(chat_id, {"queues": queues})
        else:
            raise QueueNotFoundError(f"queue ({queue_id}) not found in chat {chat_id}")

    async def clear_queue_expiration(self, chat_id: int, queue_id: str):
        """Удаляет поле expiration у очереди.

        Тихо ничего не делает, если документ чата или очередь отсутствуют —
        это позволяет вызывать метод после удаления очереди.
        """
        doc = await self.get_chat(chat_id)
        if not doc:
            # чат уже удалён — ничего делать не нужно
            return

        queues = doc.get("queues", {})
        if queue_id in queues and queues[queue_id].get("expiration"):
            queues[queue_id].pop("expiration", None)
            await self.update_chat(chat_id, {"queues": queues})

    async def get_all_chats_with_queues(self) -> list[dict]:
        """Возвращает список документов: {'chat_id': int, 'chat_title': str, 'queues': {...}}"""
        cur = queue_collection.find({}, {"chat_id": 1, "queues": 1, "chat_title": 1})
        return [
            {"chat_id": doc.get("chat_id"), "chat_title": doc.get("chat_title"), "queues": doc.get("queues", {})}
            async for doc in cur
        ]

    async def rename_queue(self, chat_id: int, old_name: str, new_name: str):
        doc = await self.get_chat(chat_id)
        if not doc:
            raise ChatNotFoundError(f"chat {chat_id} not found")

        queues = doc.get("queues", {})
        target_qid = None
        for qid, q in queues.items():
            if q.get("name") == old_name:
                target_qid = qid
                break

        if target_qid is not None:
            queues[target_qid]["name"] = new_name
            await self.update_chat(chat_id, {"queues": queues})
        else:
            # Old queue doesn't exist, create new one with generated id
            queue_id = uuid4().hex[:8]
            new_queue = {
                "id": queue_id,
                "name": new_name,
                "members": [],
                "last_queue_message_id": None,
                "last_modified": await get_now(),
            }
            queues[queue_id] = new_queue
            await self.update_chat(chat_id, {"queues": queues})

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
