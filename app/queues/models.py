from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from app.queues.errors import InvalidPositionError, MembersNotFoundError, UserNotFoundError


@dataclass()
class ActionContext:
    chat_id: int = 0
    chat_title: str = ""
    queue_id: str = ""
    queue_name: str = ""
    actor: str = ""
    thread_id: Optional[int] = None


@dataclass()
class Member:
    """Класс, представляющий участника очереди."""

    user_id: int = None
    display_name: str = ""

    def to_dict(self):
        return {"user_id": self.user_id, "display_name": self.display_name}


@dataclass()
class Queue:
    """Класс, представляющий модель очереди."""

    id: str
    name: str = ""
    members: List[Member] = field(default_factory=list)
    description: str = None
    last_queue_message_id: Optional[int] = None
    last_modified: Optional[datetime] = None
    expiration: Optional[datetime] = None

    def insert(self, user_name: str, desired_pos: Optional[int] = None, user_id: int = None):
        """
        Вставляет нового пользователя в очередь.
        - user_name: Отображаемое имя пользователя.
        - desired_pos: Желаемая позиция (индекс). Если None, добавляет в конец.
        - user_id: Уникальный ID пользователя.
        """
        # Проверяем, нет ли уже такого пользователя в очереди
        if user_id and any(member.user_id == user_id for member in self.members):
            raise ValueError(f"Пользователь с ID {user_id} уже находится в очереди.")

        new_member = Member(user_id=user_id, display_name=user_name)

        old_position = None
        idx = next((i for i, user in enumerate(self.members) if user.display_name == user_name), None)
        if idx is not None:
            old_position = idx + 1
            self.members.pop(idx)

        if desired_pos is None:
            desired_pos = len(self.members)

        desired_pos = max(0, min(desired_pos, len(self.members)))

        self.members.insert(desired_pos, new_member)

        return old_position, desired_pos + 1

    def remove(self, user_name: str):
        """Удаляет пользователя из очереди по его user_id."""
        if not self.members:
            raise MembersNotFoundError("Невозможно извлечь участника из пустой очереди.")

        idx = next((i for i, user in enumerate(self.members) if user.display_name == user_name), None)
        if idx is None:
            raise UserNotFoundError(f"user '{user_name}' not found in queue")
        user = self.members.pop(idx)
        removed_name = user.display_name

        return removed_name, idx + 1

    def pop(self, pos: int = -1) -> Member:
        """
        Удаляет и возвращает участника с указанной позиции (по умолчанию — последнего).
        """

        if not self.members:
            raise MembersNotFoundError("Невозможно извлечь участника из пустой очереди.")

        if not (0 <= pos < len(self.members)):
            raise InvalidPositionError("position out of range")

        user = self.members.pop(pos)
        removed_name = user.display_name

        return removed_name, pos + 1

    def swap_by_position(self, pos1: int, pos2: int):
        """
        Меняет местами двух участников по их позициям (индексам).
        """
        if not self.members:
            raise MembersNotFoundError("Невозможно извлечь участника из пустой очереди.")

        if pos1 < 0 or pos2 < 0 or pos1 >= len(self.members) or pos2 >= len(self.members):
            raise InvalidPositionError("Positions out of range")

        if pos1 == pos2:
            raise InvalidPositionError("Positions are equal")

        user1, user2 = self.members[pos1], self.members[pos2]
        self.members[pos1], self.members[pos2] = user2, user1

        return pos1 + 1, pos2 + 1, user1.display_name, user2.display_name

    def swap_by_name(self, user_name1: str, user_name2: str):
        """
        Меняет местами двух участников по их именам.
        """
        pos1, pos2 = None, None
        for i, user in enumerate(self.members):
            if user.display_name == user_name1:
                pos1 = i
            elif user.display_name == user_name2:
                pos2 = i
        if pos1 is None or pos2 is None:
            raise UserNotFoundError("One or both names not found")

        return self.swap_by_position(pos1, pos2)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "members": [user.to_dict() for user in self.members],
            "description": self.description,
            "last_queue_message_id": self.last_queue_message_id,
            "last_modified": self.last_modified,
            "expiration": self.expiration,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Queue":
        """
        Создает экземпляр QueueModel из словаря.
        """
        members_list = [Member(**member_data) for member_data in data.get("members", [])]

        name = data.get("name", "")
        last_queue_message_id = data.get("last_queue_message_id")
        description = data.get("description")

        last_modified = None
        if data.get("last_modified"):
            lm = data["last_modified"]
            if isinstance(lm, dict) and lm.get("$date"):
                last_modified = datetime.fromisoformat(lm["$date"].replace("Z", "+00:00"))
            elif isinstance(lm, datetime):
                last_modified = lm

        expiration = None
        if data.get("expiration"):
            exp = data["expiration"]
            if isinstance(exp, dict) and exp.get("$date"):
                expiration = datetime.fromisoformat(exp["$date"].replace("Z", "+00:00"))
            elif isinstance(exp, datetime):
                expiration = exp

        return cls(
            id=data.get("id", ""),
            name=name,
            members=members_list,
            description=description,
            last_queue_message_id=last_queue_message_id,
            last_modified=last_modified,
            expiration=expiration,
        )
