from telegram import InlineKeyboardButton, InlineKeyboardMarkup


async def queue_menu_keyboard(queue_index: int):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔄 Обновить сообщение с очередью", callback_data=f"menu|queue|{queue_index}|refresh"
                )
            ],
            [InlineKeyboardButton("🔃 Поменяться местами", callback_data=f"menu|queue|{queue_index}|swap")],
            [InlineKeyboardButton("🗑 Удалить очередь", callback_data=f"menu|queue|{queue_index}|delete")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data=f"menu|queue|{queue_index}|back"),
                InlineKeyboardButton(text="⏸️ Скрыть", callback_data="menu|queues|all|hide"),
            ],
        ]
    )


async def queues_menu_keyboard(queues_list):
    keyboard = []
    for i, queue_name in enumerate(queues_list):
        button = InlineKeyboardButton(text=f"{queue_name}", callback_data=f"menu|queues|{i}|get")

        keyboard.append([button])
    keyboard.append([InlineKeyboardButton(text="⏸️ Скрыть", callback_data="menu|queues|all|hide")])

    return InlineKeyboardMarkup(keyboard)


async def queue_swap_keyboard(queue, queue_index):
    keyboard = []
    for i, user in enumerate(queue):
        # expect user to be dict {user_id, display_name}
        text = user.get("display_name") or str(user.get("user_id"))
        cb = f"queue|{queue_index}|swap|{user.get('user_id')}"
        button = InlineKeyboardButton(text=f"{text}", callback_data=cb)
        keyboard.append([button])
    keyboard.append(
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"menu|queues|{queue_index}|get"),
            InlineKeyboardButton(text="⏸️ Скрыть", callback_data="menu|queues|all|hide"),
        ]
    )

    return InlineKeyboardMarkup(keyboard)
