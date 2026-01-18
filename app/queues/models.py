from dataclasses import dataclass
from typing import Optional


@dataclass()
class ActionContext:
    chat_id: int = 0
    chat_title: str = ""
    queue_id: str = ""
    queue_name: str = ""
    actor: str = ""
    thread_id: Optional[int] = None
