from typing import Dict, List, Optional

from .errors import InvalidPositionError, MembersNotFoundError, UserNotFoundError


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
    def remove_by_position(members: List[dict], pos: int) -> tuple[str, int]:
        """Remove by position (1-based).

        Raises:
            InvalidPositionError: _description_

        Returns:
            (removed_name, position)
        """
        print(pos)
        try:
            pos -= 1
        except TypeError:
            raise InvalidPositionError("Position is not an integer")

        if members is None:
            raise MembersNotFoundError("Members list is None")

        if not (0 <= pos < len(members)):
            raise InvalidPositionError("position out of range")

        user = members.pop(pos)
        removed_name = user.get("display_name")
        return removed_name, pos + 1

    @staticmethod
    def remove_by_name(members: List[dict], user_name: str) -> tuple[str, int]:
        """Remove by display_name.

        Returns:
            (removed_name, position)."""
        if members is None:
            raise MembersNotFoundError("Members list is None")

        idx = next((i for i, user in enumerate(members or []) if user.get("display_name") == user_name), None)
        if idx is None:
            raise UserNotFoundError(f"user '{user_name}' not found in queue")

        user = members.pop(idx)
        removed_name = user.get("display_name")
        return removed_name, idx + 1

    @staticmethod
    def insert_at_position(
        members: List[dict], user_name: str, desired_pos: Optional[int] = None
    ) -> tuple[str, int, Optional[int]]:
        """
        Insert user_name into items at desired_pos (0-based). If desired_pos is None -> append.
        If user already exists — remove old and return old_position (1-based).
        Returns: (user_name, new_position(1-based), old_position(1-based)|None)
        """
        if members is None:
            raise MembersNotFoundError("Members list is None")

        old_position = None
        idx = next((i for i, user in enumerate(members) if user.get("display_name") == user_name), None)
        if idx is not None:
            old_position = idx + 1
            members.pop(idx)

        if desired_pos is None:
            desired_pos = len(members)

        desired_pos = max(0, min(desired_pos, len(members)))

        members.insert(desired_pos, {"user_id": None, "display_name": user_name})
        return user_name, desired_pos + 1, old_position

    @staticmethod
    def replace_by_positions(members: List[dict], pos1: int, pos2: int):
        """Swap users at pos1 and pos2 (1-based).

        Raises:
            InvalidPositionError

        Returns:
            pos1, pos2, name1, name2
        """
        if members is None:
            raise MembersNotFoundError("Members list is None")

        try:
            pos1 -= 1
            pos2 -= 1
        except TypeError:
            raise InvalidPositionError("Positions is not an integer")

        if pos1 < 0 or pos2 < 0 or pos1 >= len(members) or pos2 >= len(members):
            raise InvalidPositionError("Positions out of range")

        if pos1 == pos2:
            raise InvalidPositionError("Positions are equal")

        user1, user2 = members[pos1], members[pos2]
        members[pos1], members[pos2] = user2, user1

        return pos1 + 1, pos2 + 1, user1.get("display_name"), user2.get("display_name")

    @staticmethod
    def replace_by_names(members: List[dict], name1: str, name2: str):
        # find by display_name
        pos1 = next((i for i, user in enumerate(members) if user.get("display_name") == name1), None)
        pos2 = next((i for i, user in enumerate(members) if user.get("display_name") == name2), None)
        if pos1 is None or pos2 is None:
            raise UserNotFoundError("One or both names not found")

        return QueueDomainService.replace_by_positions(members, pos1 + 1, pos2 + 1)
