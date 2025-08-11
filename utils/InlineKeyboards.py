# Создание inline-клавиатуры для сообщений очереди.
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def queue_keyboard(queue_name):
    keyboard = [
        [
            InlineKeyboardButton("🔼 Встать", callback_data = f"queue|{queue_name}|join"),
            InlineKeyboardButton("🔽 Выйти", callback_data=f"queue|{queue_name}|leave")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def queues_keyboard(queues_list):
    keyboard = []
    for i, queue_name in enumerate(queues_list.keys()):

        button = InlineKeyboardButton(text=f"{queue_name}", callback_data=f"queues|{queue_name}|get")
        # Кнопка с иконкой корзины для удаления
        delete_button = InlineKeyboardButton(text="🗑️", callback_data=f"queues|{queue_name}|delete")

        keyboard.append([button, delete_button])

    return InlineKeyboardMarkup(keyboard)
