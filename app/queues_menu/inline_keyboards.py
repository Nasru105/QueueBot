from typing import Any, Dict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


async def queue_menu_keyboard(queue_id: int):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔄 Обновить сообщение с очередью", callback_data=f"menu|queue|{queue_id}|refresh")],
            [InlineKeyboardButton("🔃 Поменяться местами", callback_data=f"menu|queue|{queue_id}|swap")],
            [InlineKeyboardButton("🗑 Удалить очередь", callback_data=f"menu|queue|{queue_id}|delete")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data=f"menu|queue|{queue_id}|back"),
                InlineKeyboardButton(text="⏸️ Скрыть", callback_data="menu|queues|all|hide"),
            ],
        ]
    )


async def queues_menu_keyboard(queues: Dict[str, Dict[str, Any]]):
    keyboard = []
    for queue_id, queue in queues.items():
        button = InlineKeyboardButton(text=f"{queue['name']}", callback_data=f"menu|queues|{queue_id}|get")

        keyboard.append([button])
    keyboard.append([InlineKeyboardButton(text="⏸️ Скрыть", callback_data="menu|queues|all|hide")])

    return InlineKeyboardMarkup(keyboard)
