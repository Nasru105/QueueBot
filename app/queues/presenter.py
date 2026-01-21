from typing import Callable, Dict, Optional

from telegram import InlineKeyboardMarkup
from telegram.helpers import escape_markdown

from app.queues.inline_keyboards import queue_keyboard

from .models import Queue


class QueuePresenter:
    """
    Формирование текста очереди и клавиатур (presentation).
    keyboard_factory — callable(index: int) -> InlineKeyboardMarkup
    """

    def __init__(self, keyboard_factory: Optional[Callable[[int], InlineKeyboardMarkup]] = None):
        self.keyboard_factory = keyboard_factory

    @staticmethod
    def generate_queue_name(queues: Dict[str, Queue], base: str = "Очередь") -> str:
        i = 1

        queues = {queue.name: queue.members for queue in queues.values()}
        while queues.get(f"{base} {i}", []):
            i += 1
        return f"{base} {i}"

    @staticmethod
    def format_queue_text(queue: Queue) -> str:
        """Format queue text for display.

        Accepts members as either list of strings (display names) or list of dicts
        with keys `display_name` and/or `member_id`.
        """
        name_escaped = escape_markdown(queue.name, version=2)

        description = ""
        if queue.description:
            description = f"{escape_markdown(queue.description, version=2)}\n\n"

        members = []
        if not queue.members:
            members = ["Очередь пуста\\."]
        for i, user in enumerate(queue.members):
            display = user.display_name or str(user.user_id)
            members.append(f"{i + 1}\\. {escape_markdown(display, version=2)}")

        return f"*`{name_escaped}`*\n\n" + description + "\n".join(members)

    def build_queue_keyboard(self, queue_id: int) -> Optional[InlineKeyboardMarkup]:
        return queue_keyboard(queue_id)
