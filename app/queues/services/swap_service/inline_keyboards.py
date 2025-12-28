from telegram import InlineKeyboardButton, InlineKeyboardMarkup


async def queue_swap_keyboard(members, queue_id):
    keyboard = []
    for user in members:
        if user.get("user_id"):
            text = user.get("display_name") or str(user.get("user_id"))
            cb = f"queue|{queue_id}|swap|request|{user.get('user_id')}"
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
