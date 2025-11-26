from typing import List, Optional

from .models import InsertResult, RemoveResult, ReplaceResult


class QueueDomainService:
    """
    Чистая бизнес-логика работы с очередью (in-memory logic).
    Методы не взаимодействуют с Telegram или репо — принимают/возвращают data structures.
    """

    @staticmethod
    def generate_queue_name(existing_names: List[str], base: str = "Очередь") -> str:
        i = 1
        names_set = set(existing_names)
        while f"{base} {i}" in names_set:
            i += 1
        return f"{base} {i}"

    @staticmethod
    def remove_by_pos_or_name(queue: List[str], args: list[str]) -> RemoveResult:
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
                removed_name = working.pop(pos)
                position = pos + 1
        except Exception:
            # by name
            user_name = " ".join(args).strip()
            if user_name and user_name in working:
                pos = working.index(user_name)
                removed_name = user_name
                position = pos + 1
                working.remove(user_name)

        if removed_name is None:
            return RemoveResult(None, None, None)

        return RemoveResult(removed_name, position, working)

    @staticmethod
    def insert_at_position(queue: List[str], user_name: str, desired_pos: Optional[int]) -> InsertResult:
        """
        Insert user_name into items at desired_pos (0-based). If desired_pos is None -> append.
        If user already exists — remove old and return old_position (1-based).
        Returns InsertResult(user_name, new_position(1-based), updated_queue, old_position(1-based)|None)
        """
        if queue is None:
            return InsertResult(None, None, None, None)

        # normalize desired_pos
        if desired_pos is None:
            desired_pos = len(queue)

        old_position = None
        if user_name in queue:
            old_position = queue.index(user_name) + 1
            queue.remove(user_name)

        desired_pos = max(0, min(desired_pos, len(queue)))
        queue.insert(desired_pos, user_name)
        return InsertResult(user_name, desired_pos + 1, queue, old_position)

    @staticmethod
    def replace_by_positions(queue: List[str], pos1: int, pos2: int, queue_name: str) -> ReplaceResult:
        if pos1 < 0 or pos2 < 0 or pos1 >= len(queue) or pos2 >= len(queue):
            raise ValueError("Positions out of range")

        if pos1 == pos2:
            raise ValueError("Positions are equal")

        print(queue, pos1, pos2)

        user1, user2 = queue[pos1], queue[pos2]
        queue[pos1], queue[pos2] = user2, user1

        return ReplaceResult(queue_name=queue_name, updated_queue=queue, pos1=pos1, pos2=pos2, user1=user1, user2=user2)

    @staticmethod
    def replace_by_names(queue: List[str], name1: str, name2: str, queue_name: str) -> ReplaceResult:
        if name1 not in queue or name2 not in queue:
            raise ValueError("One or both names not found")

        pos1 = queue.index(name1)
        pos2 = queue.index(name2)

        return QueueDomainService.replace_by_positions(queue, pos1, pos2, queue_name)
