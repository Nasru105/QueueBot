from typing import List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.queues.models import Member


async def queue_swap_keyboard(members: List[Member], queue_id):
    keyboard = []
    for user in members:
        if user.user_id is not None:
            text = user.display_name or str(user.user_id)
            cb = f"queue|{queue_id}|swap|request|{user.user_id}"
            button = InlineKeyboardButton(text=f"{text}", callback_data=cb)
            keyboard.append([button])

    keyboard.append(
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"menu|queues|{queue_id}|get"),
            InlineKeyboardButton(text="⏸️ Скрыть", callback_data="menu|queues|all|hide"),
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def swap_confirmation_keyboard(queue_id: str, swap_id: str) -> InlineKeyboardMarkup:
    """Build keyboard for confirming/declining a swap request."""
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text="Да", callback_data=f"queue|{queue_id}|swap|accept|{swap_id}"),
                InlineKeyboardButton(text="Нет", callback_data=f"queue|{queue_id}|swap|decline|{swap_id}"),
            ],
        ]
    )
    return keyboard
