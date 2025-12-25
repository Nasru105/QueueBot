from typing import Any, Dict, List, Optional
from uuid import uuid4

from telegram import User

from app.services.mongo_storage import queue_collection, user_collection
from app.utils.utils import get_now_formatted_time, strip_user_full_name

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
        queues[queue_id]["last_modified"] = await get_now_formatted_time()
        await self.update_chat(chat_id, {"queues": queues})
        return len(queue)

    # async def add_to_queue_by_name(self, chat_id: int, queue_name: str, user_id: int, display_name: str) -> int:
    #     doc = await self.get_chat(chat_id)
    #     if not doc:
    #         raise ChatNotFoundError(f"chat {chat_id} not found")

    #     queues = doc.get("queues", {})
    #     target_qid = None
    #     for qid, q in queues.items():
    #         if q.get("name") == queue_name:
    #             target_qid = qid
    #             break

    #     if target_qid is None:
    #         raise QueueNotFoundError(f"queue '{queue_name}' not found in chat {chat_id}")

    #     queue_list = queues[target_qid].setdefault("queue", [])
    #     # queue_list now stores dicts: {"user_id": int, "display_name": str}
    #     if any(u.get("user_id") == user_id for u in queue_list):
    #         raise UserAlreadyExistsError(f"user {user_id} already in queue")

    #     queue_list.append({"user_id": user_id, "display_name": display_name})
    #     queues[target_qid]["last_modified"] = await get_now_formatted_time()
    #     await self.update_chat(chat_id, {"queues": queues})
    #     return len(queue_list)

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
        queues[queue_id]["last_modified"] = await get_now_formatted_time()
        await self.update_chat(chat_id, {"queues": queues})
        return position

    # async def remove_from_queue_by_name(self, chat_id: int, queue_name: str, user_id: int) -> Optional[int]:
    # doc = await self.get_chat(chat_id)
    # if not doc:
    #     raise ChatNotFoundError(f"chat {chat_id} not found")

    # queues = doc.get("queues", {})
    # target_qid = None
    # for qid, q in queues.items():
    #     if q.get("name") == queue_name:
    #         target_qid = qid
    #         break

    # if target_qid is None:
    #     raise QueueNotFoundError(f"queue '{queue_name}' not found in chat {chat_id}")

    # queue_list = queues[target_qid].get("queue", [])
    # # find by user_id
    # idx = next((i for i, u in enumerate(queue_list) if u.get("user_id") == user_id), None)
    # if idx is None:
    #     raise UserNotFoundError(f"user id '{user_id}' not found in queue '{queue_name}'")

    # position = idx + 1
    # queue_list.pop(idx)
    # queues[target_qid]["last_modified"] = await get_now_formatted_time()
    # await self.update_chat(chat_id, {"queues": queues})
    # return position

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
            "last_modified": await get_now_formatted_time(),
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

    # async def delete_queue_by_name(self, chat_id: int, queue_name: str) -> bool:
    #     """
    #     Удаляет очередь по имени.
    #     Если это была последняя очередь — полностью удаляет документ чата.
    #     """
    #     # Получаем документ
    #     doc = await queue_collection.find_one({"chat_id": chat_id})
    #     if not doc:
    #         raise ChatNotFoundError(f"chat {chat_id} not found")

    #     queues = doc.get("queues", {}) or {}

    #     # Найти ключ, соответствующий имени очереди
    #     key_to_remove = None
    #     for qid, q in queues.items():
    #         if q.get("name") == queue_name:
    #             key_to_remove = qid
    #             break

    #     if key_to_remove is None:
    #         # Очередь не найдена
    #         raise QueueNotFoundError(f"queue '{queue_name}' not found in chat {chat_id}")

    #     # Удаляем очередь
    #     del queues[key_to_remove]

    #     if not queues:
    #         # Это была последняя очередь → удаляем весь документ
    #         await queue_collection.delete_one({"chat_id": chat_id})
    #     else:
    #         # Остались другие очереди → обновляем словарь
    #         await queue_collection.update_one({"chat_id": chat_id}, {"$set": {"queues": queues}})

    async def update_queue(self, chat_id: int, queue_id: str, new_members: List[dict]):
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
            queues[queue_id]["last_modified"] = await get_now_formatted_time()
            await self.update_chat(chat_id, {"queues": queues})
        else:
            raise QueueNotFoundError(f"queue '{queue_id}' not found in chat {chat_id}")

    # async def update_queue_by_name(self, chat_id: int, queue_name: str, new_queue: List[dict]):
    #     """
    #     Обновляет список пользователей в очереди.

    #     :param chat_id: ID чата
    #     :param queue_name: Имя очереди
    #     :param new_queue: Новый список пользователей (List[str])
    #     """
    #     doc = await self.get_chat(chat_id)
    #     if not doc:
    #         raise ChatNotFoundError(f"chat {chat_id} not found")

    #     queues = doc.get("queues", {}) or {}
    #     target_qid = None
    #     for qid, q in queues.items():
    #         if q.get("name") == queue_name:
    #             target_qid = qid
    #             break

    #     if target_qid is not None:
    #         # expect new_queue to be list of dicts
    #         queues[target_qid]["queue"] = new_queue
    #         queues[target_qid]["last_modified"] = await get_now_formatted_time()
    #         await self.update_chat(chat_id, {"queues": queues})
    #     else:
    #         raise QueueNotFoundError(f"queue '{queue_name}' not found in chat {chat_id}")

    async def get_last_modified_time(self, chat_id: int, queue_id: str) -> Optional[int]:
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
                "last_modified": await get_now_formatted_time(),
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

    # async def attach_user_id_by_display_name(
    #     self, chat_id: int, queue_name: str, display_name: str, user_id: int
    # ) -> Optional[int]:
    #     """Если в очереди есть элемент с display_name, то привязать к нему user_id и вернуть индекс (0-based).
    #     Если не найдено — вернуть None.
    #     """
    #     doc = await self.get_chat(chat_id)
    #     if not doc:
    #         raise ChatNotFoundError(f"chat {chat_id} not found")

    #     queues = doc.get("queues", {}) or {}
    #     target_qid = None
    #     for qid, q in queues.items():
    #         if q.get("name") == queue_name:
    #             target_qid = qid
    #             break

    #     if target_qid is None:
    #         raise QueueNotFoundError(f"queue '{queue_name}' not found in chat {chat_id}")

    #     queue_list = queues[target_qid].setdefault("queue", [])
    #     for idx, item in enumerate(queue_list):
    #         # item might be plain string (legacy) or dict
    #         if isinstance(item, dict):
    #             if item.get("display_name") == display_name:
    #                 if item.get("user_id") != user_id:
    #                     item["user_id"] = user_id
    #                     queues[target_qid]["last_modified"] = await get_now_formatted_time()
    #                     await self.update_chat(chat_id, {"queues": queues})
    #                 return idx
    #         else:
    #             if str(item) == display_name:
    #                 # convert legacy string to dict
    #                 queue_list[idx] = {"user_id": user_id, "display_name": display_name}
    #                 queues[target_qid]["last_modified"] = await get_now_formatted_time()
    #                 await self.update_chat(chat_id, {"queues": queues})
    #                 return idx

    #     return None

    async def update_user_display_name(self, user_id: int, display_names: Dict[str, str]):
        await user_collection.update_one({"user_id": user_id}, {"$set": {"display_names": display_names}}, upsert=True)
