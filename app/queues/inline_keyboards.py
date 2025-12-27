from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def queue_keyboard(queue_id: int):
    keyboard = [
        [
            InlineKeyboardButton("🔼 Встать", callback_data=f"queue|{queue_id}|join"),
            InlineKeyboardButton("🔽 Выйти", callback_data=f"queue|{queue_id}|leave"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
