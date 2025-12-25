# app/utils/InlineKeyboards.py

# Создание inline-клавиатуры для сообщений очереди.
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def queue_keyboard(queue_id: int):
    # Убедимся, что индекс неотрицательный
    keyboard = [
        [
            InlineKeyboardButton("🔼 Встать", callback_data=f"queue|{queue_id}|join"),
            InlineKeyboardButton("🔽 Выйти", callback_data=f"queue|{queue_id}|leave"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
