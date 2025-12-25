from typing import Any, Dict, List, Optional

from .errors import InvalidPositionError, UserNotFoundError
from .models import InsertResult, RemoveResult, ReplaceResult


class QueueDomainService:
    """
    Чистая бизнес-логика работы с очередью (in-memory logic).
    Методы не взаимодействуют с Telegram или репо — принимают/возвращают data structures.
    """

    @staticmethod
    def generate_queue_name(queues: Dict, base: str = "Очередь") -> str:
        i = 1

        queues = {queue["name"]: queue["members"] for queue in queues.values()}
        while queues.get(f"{base} {i}", []):
            i += 1
        return f"{base} {i}"

    @staticmethod
    def _display_name(item: Any) -> str:
        if isinstance(item, dict):
            return item.get("display_name") or str(item.get("user_id"))
        return str(item)

    @staticmethod
    def _user_id(item: Any) -> Optional[int]:
        if isinstance(item, dict):
            return item.get("user_id")
        return None

    @staticmethod
    def remove_by_pos_or_name(queue: List[dict], args: list[str]) -> RemoveResult:
        """
        Попробовать удалить по позиции (args[0]), иначе по имени (join args).
        Возвращает RemoveResult(removed_name, position(1-based), updated_queue)
        """
        if queue is None:
            return RemoveResult(None, None, None)

        working = list(queue)
        removed_name = None
        position = None

        # try by position
        try:
            pos = int(args[0]) - 1
            if 0 <= pos < len(working):
                item = working.pop(pos)
                removed_name = QueueDomainService._display_name(item)
                position = pos + 1
            else:
                raise InvalidPositionError("position out of range")
        except ValueError:
            # by name
            user_name = " ".join(args).strip()
            # find by display_name
            idx = next((i for i, it in enumerate(working) if QueueDomainService._display_name(it) == user_name), None)
            if user_name and idx is not None:
                item = working.pop(idx)
                removed_name = QueueDomainService._display_name(item)
                position = idx + 1
            else:
                raise UserNotFoundError(f"user '{user_name}' not found in queue")

        if removed_name is None:
            return RemoveResult(None, None, None)

        return RemoveResult(removed_name, position, working)

    @staticmethod
    def insert_at_position(queue: List[dict], user_name: str, desired_pos: Optional[int]) -> InsertResult:
        """
        Insert user_name into items at desired_pos (0-based). If desired_pos is None -> append.
        If user already exists — remove old and return old_position (1-based).
        Returns InsertResult(user_name, new_position(1-based), updated_queue, old_position(1-based)|None)
        """
        if queue is None:
            return InsertResult(None, None, None, None)

        old_position = None
        idx = next((i for i, user in enumerate(queue) if QueueDomainService._display_name(user) == user_name), None)
        if idx is not None:
            old_position = idx + 1
            queue.pop(idx)

        if desired_pos is None:
            desired_pos = len(queue)

        desired_pos = max(0, min(desired_pos, len(queue)))

        queue.insert(desired_pos, {"user_id": None, "display_name": user_name})
        return InsertResult(user_name, desired_pos + 1, queue, old_position)

    @staticmethod
    def replace_by_positions(queue: List[dict], pos1: int, pos2: int, queue_name: str) -> ReplaceResult:
        if pos1 < 0 or pos2 < 0 or pos1 >= len(queue) or pos2 >= len(queue):
            raise InvalidPositionError("Positions out of range")

        if pos1 == pos2:
            raise InvalidPositionError("Positions are equal")

        user1, user2 = queue[pos1], queue[pos2]
        queue[pos1], queue[pos2] = user2, user1

        return ReplaceResult(
            queue_name=queue_name,
            updated_queue=queue,
            pos1=pos1,
            pos2=pos2,
            user1=QueueDomainService._display_name(user1),
            user2=QueueDomainService._display_name(user2),
        )

    @staticmethod
    def replace_by_names(queue: List[dict], name1: str, name2: str, queue_name: str) -> ReplaceResult:
        # find by display_name
        pos1 = next((i for i, it in enumerate(queue) if QueueDomainService._display_name(it) == name1), None)
        pos2 = next((i for i, it in enumerate(queue) if QueueDomainService._display_name(it) == name2), None)
        if pos1 is None or pos2 is None:
            raise UserNotFoundError("One or both names not found")

        return QueueDomainService.replace_by_positions(queue, pos1, pos2, queue_name)
