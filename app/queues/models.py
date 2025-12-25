from dataclasses import dataclass
from typing import Any, Dict, List, NamedTuple, Optional


@dataclass()
class ActionContext:
    chat_id: int = 0
    chat_title: str = ""
    queue_id: str = ""
    queue_name: str = ""
    actor: str = ""
    thread_id: Optional[int] = None


@dataclass
class QueueEntity:
    chat_id: int
    name: str
    items: List[Dict[str, Any]]
    last_queue_message_id: Optional[int] = None


class RemoveResult(NamedTuple):
    removed_name: Optional[str]
    position: Optional[int]  # 1-based
    updated_queue: Optional[List[Dict[str, Any]]]


class InsertResult(NamedTuple):
    user_name: Optional[str]
    position: Optional[int]  # 1-based
    updated_queue: Optional[List[Dict[str, Any]]]
    old_position: Optional[int]  # 1-based or None


class ReplaceResult(NamedTuple):
    queue_name: str
    updated_queue: List[Dict[str, Any]]
    pos1: int
    pos2: int
    user1: str
    user2: str
