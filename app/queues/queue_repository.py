from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase
from telegram import User

from app.utils.utils import get_now, strip_user_full_name

from .errors import QueueNotFoundError, UserAlreadyExistsError, UserNotFoundError
from .models import Queue


class QueueRepository:
    """Низкоуровневые операции с MongoDB"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.queue_collection = db["queue_data"]
        self.user_collection = db["user_data"]

    async def get_chat(self, chat_id: int) -> Dict:
        doc = await self.queue_collection.find_one({"chat_id": chat_id})
        if not doc:
            doc = {"chat_id": chat_id, "queues": {}, "last_list_message_id": None}
            await self.queue_collection.insert_one(doc)
        return doc

    async def update_chat(self, chat_id: int, update: Dict[str, Any]):
        await self.queue_collection.update_one({"chat_id": chat_id}, {"$set": update}, upsert=True)

    async def get_queue(self, chat_id: int, queue_id: int) -> Queue:
        doc = await self.get_chat(chat_id)
        queues: dict = doc.setdefault("queues", {})

        if queue_id not in queues:
            raise QueueNotFoundError(f"queue ({queue_id}) not found in chat {chat_id}")

        return Queue.from_dict(queues[queue_id])

    async def get_queue_by_name(self, chat_id: int, queue_name: str) -> Queue:
        doc = await self.get_chat(chat_id)
        queues = doc.setdefault("queues", {})
        for queue in queues.values():
            if queue.get("name") == queue_name:
                return Queue.from_dict(queue)
        raise QueueNotFoundError(f"queue '{queue_name}' not found in chat {chat_id}")

    async def add_to_queue(self, chat_id: int, queue_id: str, user_id: int, display_name: str) -> int:
        doc = await self.get_chat(chat_id)
        queues = doc.setdefault("queues", {})
        queue = queues.setdefault(queue_id, {})
        members = queue.setdefault("members", [])

        if any(member.get("user_id") == user_id for member in members):
            raise UserAlreadyExistsError(f"user {user_id} already in queue")

        members.append({"user_id": user_id, "display_name": display_name})
        queue["last_modified"] = get_now()
        await self.update_chat(chat_id, {f"queues.{queue_id}": queue})

        return len(members)

    async def remove_from_queue(self, chat_id: int, queue_id: str, user_id: int) -> Optional[int]:
        doc = await self.get_chat(chat_id)
        queues = doc.setdefault("queues", {})
        queue = queues.setdefault(queue_id, {})
        members = queue.setdefault("members", [])

        idx = next((i for i, user in enumerate(members) if user.get("user_id") == user_id), None)
        if idx is None:
            raise UserNotFoundError(f"user id '{user_id}' not found in queue '{queue_id}'")

        position = idx + 1
        members.pop(idx)
        queue["last_modified"] = get_now()
        await self.update_chat(chat_id, {f"queues.{queue_id}": queue})

        return position

    async def create_queue(self, chat_id: int, chat_title: str, queue_name: str) -> str:
        doc = await self.get_chat(chat_id)
        doc["chat_title"] = chat_title

        queues: dict = doc.setdefault("queues", {})

        for queue in queues.values():
            if queue.get("name") == queue_name:
                return queue.get("id")

        queue_id = uuid4().hex[:8]

        new_queue = {
            "id": queue_id,
            "name": queue_name,
            "description": None,
            "members": [],
            "last_queue_message_id": None,
            "last_modified": get_now(),
        }

        queues[queue_id] = new_queue

        await self.update_chat(chat_id, {"queues": queues})
        return queue_id

    async def delete_queue(self, chat_id: int, queue_id: str) -> bool:
        """
        Удаляет очередь.
        Если это была последняя очередь — полностью удаляет документ чата.
        """
        doc = await self.get_chat(chat_id)
        queues: dict = doc.setdefault("queues", {})

        if queue_id not in queues:
            raise QueueNotFoundError(f"queue '{queue_id}' not found in chat {chat_id}")

        del queues[queue_id]

        if not queues:
            await self.queue_collection.delete_one({"chat_id": chat_id})
        else:
            await self.update_chat(chat_id, {"queues": queues})

    async def update_queue(self, chat_id: int, queue: Queue):
        """Обновляет очереди."""
        queue.last_modified = get_now()
        await self.update_chat(chat_id, {f"queues.{queue.id}": queue.to_dict()})

    async def get_last_modified_time(self, chat_id: int, queue_id: str) -> Optional[datetime]:
        """Возвращает datetime или None. Поддерживает старый строковый формат."""
        doc = await self.get_chat(chat_id)
        queues = doc.setdefault("queues", {})

        if queue_id not in queues:
            raise QueueNotFoundError(f"queue ({queue_id}) not found in chat {chat_id}")

        queue = queues.get(queue_id, {})

        return queue.get("last_modified")

    async def get_queue_message_id(self, chat_id: int, queue_id: str) -> Optional[int]:
        """Получает message_id очереди."""
        doc = await self.get_chat(chat_id)
        queues = doc.setdefault("queues", {})

        if queue_id not in queues:
            raise QueueNotFoundError(
                f"Failed to get last_queue_message_id: queue ({queue_id}) not found in chat {chat_id}"
            )

        queue = queues.get(queue_id, {})
        return queue.get("last_queue_message_id")

    async def set_queue_message_id(self, chat_id: int, queue_id: str, msg_id: int):
        doc = await self.get_chat(chat_id)
        queues = doc.setdefault("queues", {})

        if queue_id not in queues:
            raise QueueNotFoundError(
                f"Failed to set last_queue_message_id: queue ({queue_id}) not found in chat {chat_id}"
            )
        queue = queues.setdefault(queue_id, {})
        queue["last_queue_message_id"] = msg_id
        await self.update_chat(chat_id, {f"queues.{queue_id}": queue})

    async def get_all_queues(self, chat_id: int) -> Dict[str, Queue]:
        doc = await self.get_chat(chat_id)
        queues = doc.get("queues", {})
        return {qid: Queue.from_dict(queue) for qid, queue in queues.items()}

    async def get_list_message_id(self, chat_id: int) -> Optional[int]:
        doc = await self.queue_collection.find_one({"chat_id": chat_id}, {"last_list_message_id": 1})
        return doc.get("last_list_message_id") if doc else None

    async def set_list_message_id(self, chat_id: int, msg_id: int):
        await self.update_chat(chat_id, {"last_list_message_id": msg_id})

    async def clear_list_message_id(self, chat_id: int):
        await self.update_chat(chat_id, {"last_list_message_id": None})

    async def get_queue_description(self, chat_id: int, queue_id: int) -> Optional[int]:
        doc = await self.get_chat(chat_id)

        return doc.get("queues", {}).get(queue_id, {}).get("description")

    async def set_queue_description(self, chat_id: int, queue_id: int, description: str = None) -> Optional[int]:
        await self.update_chat(chat_id, {f"queues.{queue_id}.description": description})

    async def clear_queue_description(self, chat_id: int, queue_id: int):
        await self.set_queue_description(chat_id, queue_id)

    async def get_queue_expiration(self, chat_id: int, queue_id: str) -> Optional[datetime]:
        """Возвращает datetime expiration или None. Поддерживает старый строковый формат."""
        doc = await self.get_chat(chat_id)

        return doc.get("queues", {}).get(queue_id, {}).get("expiration")

    async def set_queue_expiration(self, chat_id: int, queue_id: str, expiration):
        await self.update_chat(chat_id, {f"queues.{queue_id}.expiration": expiration})

    async def clear_queue_expiration(self, chat_id: int, queue_id: str):
        await self.update_chat(chat_id, {f"queues.{queue_id}.expiration": None})

    async def get_all_chats_with_queues(self) -> list[dict]:
        """Возвращает список документов: {'chat_id': int, 'chat_title': str, 'queues': {...}}"""
        cur = self.queue_collection.find({}, {"chat_id": 1, "queues": 1, "chat_title": 1})
        return [
            {"chat_id": doc.get("chat_id"), "chat_title": doc.get("chat_title"), "queues": doc.get("queues", {})}
            async for doc in cur
        ]

    async def rename_queue(self, chat_id: int, old_name: str, new_name: str):
        doc = await self.get_chat(chat_id)
        queues = doc.setdefault("queues", {})
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
                "description": None,
                "members": [],
                "last_queue_message_id": None,
                "last_modified": get_now(),
            }
            queues[queue_id] = new_queue
            await self.update_chat(chat_id, {"queues": queues})

    async def get_user_display_name(self, user: User) -> str:
        doc_user = await self.user_collection.find_one({"user_id": user.id})
        if not doc_user:
            # Первый раз видим — создаём
            doc_user = {
                "user_id": user.id,
                "username": user.username,
                "display_names": {"global": strip_user_full_name(user)},
            }
            await self.user_collection.insert_one(doc_user)
        elif doc_user.get("username", None) != user.username:
            await self.user_collection.update_one(
                {"user_id": user.id}, {"$set": {"username": user.username}}, upsert=True
            )

        return doc_user

    async def update_user_display_name(self, user_id: int, display_names: Dict[str, str]):
        await self.user_collection.update_one(
            {"user_id": user_id}, {"$set": {"display_names": display_names}}, upsert=True
        )
