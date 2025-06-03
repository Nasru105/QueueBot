from datetime import datetime
import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Безопасное удаление сообщения.
async def safe_delete(context, chat_id, message_id):
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        print(f"Не удалось удалить сообщение {message_id}: {e}")

# Создание inline-клавиатуры для сообщений очереди.
def get_queue_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🔼 Встать в очередь", callback_data="join"),
            InlineKeyboardButton("🔽 Выйти", callback_data="leave")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# Преобразование строковых ключей из JSON обратно в словари с числовыми ключами.
def reformat(queues_str, last_queue_message_str):
    queues, last_queue_message = {}, {}

    # Преобразуем ключи очередей в числа (chat_id)
    for queue in queues_str:
        queues[int(queue)] = queues_str[queue]

    # Преобразуем ключи сообщений (chat_id) в числа
    for id in last_queue_message_str:
        last_queue_message[int(id)] = last_queue_message_str[id]

    return queues, last_queue_message

def get_time():
    moscow_tz = pytz.timezone('Europe/Moscow')
    moscow_time = datetime.now(moscow_tz)
    return moscow_time.strftime("%H:%M:%S")

def get_names_by_username():
    pass