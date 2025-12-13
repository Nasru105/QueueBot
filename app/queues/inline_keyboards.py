# app/utils/InlineKeyboards.py

# Создание inline-клавиатуры для сообщений очереди.
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def queue_keyboard(queue_index: int):
    # Убедимся, что индекс неотрицательный
    queue_index = max(0, queue_index)
    keyboard = [
        [
            InlineKeyboardButton("🔼 Встать", callback_data=f"queue|{queue_index}|join"),
            InlineKeyboardButton("🔽 Выйти", callback_data=f"queue|{queue_index}|leave"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
