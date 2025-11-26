from typing import Callable, List, Optional

from telegram import InlineKeyboardMarkup
from telegram.helpers import escape_markdown


class QueuePresenter:
    """
    Формирование текста очереди и клавиатур (presentation).
    keyboard_factory — callable(index: int) -> InlineKeyboardMarkup
    """

    def __init__(self, keyboard_factory: Optional[Callable[[int], InlineKeyboardMarkup]] = None):
        self.keyboard_factory = keyboard_factory

    @staticmethod
    def format_queue_text(queue_name: str, items: List[str]) -> str:
        name_escaped = escape_markdown(queue_name, version=2)
        if not items:
            return f"*`{name_escaped}`*\n\nОчередь пуста\\."
        lines = [f"{i + 1}\\. {escape_markdown(u, version=2)}" for i, u in enumerate(items)]
        return f"*`{name_escaped}`*\n\n" + "\n".join(lines)

    def build_keyboard(self, queue_index: int) -> Optional[InlineKeyboardMarkup]:
        if not self.keyboard_factory:
            return None
        return self.keyboard_factory(queue_index)
