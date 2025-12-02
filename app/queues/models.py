from dataclasses import dataclass
from typing import List, NamedTuple, Optional


@dataclass()
class ActionContext:
    chat_id: int = 0
    chat_title: str = ""
    queue_name: str = ""
    actor: str = ""
    thread_id: Optional[int] = None


@dataclass
class QueueEntity:
    chat_id: int
    name: str
    items: List[str]
    last_queue_message_id: Optional[int] = None


class RemoveResult(NamedTuple):
    removed_name: Optional[str]
    position: Optional[int]  # 1-based
    updated_queue: Optional[List[str]]


class InsertResult(NamedTuple):
    user_name: Optional[str]
    position: Optional[int]  # 1-based
    updated_queue: Optional[List[str]]
    old_position: Optional[int]  # 1-based or None


class ReplaceResult(NamedTuple):
    queue_name: str
    updated_queue: List[str]
    pos1: int
    pos2: int
    user1: str
    user2: str
