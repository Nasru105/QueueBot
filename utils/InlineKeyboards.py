# Создание inline-клавиатуры для сообщений очереди.
from telegram import InlineKeyboardButton, InlineKeyboardMarkup



def queue_keyboard(queue_index):
    keyboard = [
        [
            InlineKeyboardButton("🔼 Встать", callback_data = f"queue|{queue_index}|join"),
            InlineKeyboardButton("🔽 Выйти", callback_data=f"queue|{queue_index}|leave")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def queues_keyboard(queues_list):

    keyboard = []
    for i, queue_name in enumerate(queues_list):
        button = InlineKeyboardButton(text=f"{queue_name}", callback_data=f"queues|{i}|get")
        # Кнопка с иконкой корзины для удаления
        delete_button = InlineKeyboardButton(text="🗑️", callback_data=f"queues|{i}|delete")

        keyboard.append([button, delete_button])
    keyboard.append([
        InlineKeyboardButton(text="Скрыть", callback_data=f"queues|all|hide"),
        InlineKeyboardButton(text="🗑️🗑️🗑️", callback_data=f"queues|all|delete")])


    return InlineKeyboardMarkup(keyboard)
