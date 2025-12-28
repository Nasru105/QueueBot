from typing import Callable, List, Optional

from telegram import InlineKeyboardMarkup
from telegram.helpers import escape_markdown

from app.queues.inline_keyboards import queue_keyboard


class QueuePresenter:
    """
    Формирование текста очереди и клавиатур (presentation).
    keyboard_factory — callable(index: int) -> InlineKeyboardMarkup
    """

    def __init__(self, keyboard_factory: Optional[Callable[[int], InlineKeyboardMarkup]] = None):
        self.keyboard_factory = keyboard_factory

    @staticmethod
    def format_queue_text(queue_name: str, members: List) -> str:
        """Format queue text for display.

        Accepts members as either list of strings (display names) or list of dicts
        with keys `display_name` and/or `user_id`.
        """
        name_escaped = escape_markdown(queue_name, version=2)
        if not members:
            return f"*`{name_escaped}`*\n\nОчередь пуста\\."
        lines = []
        for i, user in enumerate(members):
            display = user.get("display_name") or str(user.get("user_id"))
            lines.append(f"{i + 1}\\. {escape_markdown(display, version=2)}")
        return f"*`{name_escaped}`*\n\n" + "\n".join(lines)

    def build_queue_keyboard(self, queue_id: int) -> Optional[InlineKeyboardMarkup]:
        return queue_keyboard(queue_id)
