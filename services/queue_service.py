from services.storage import load_data, save_data
from utils.utils import reformat

# Загружаем сохранённые данные из файла и приводим ключи к нужному формату (int вместо str)
queues, last_queue_message = reformat(*load_data())

# Добавление пользователя в очередь
def add_to_queue(chat_id, user):
    queues.setdefault(chat_id, [])  # Если для чата ещё нет очереди — создаём пустую
    if user not in queues[chat_id]:  # Добавляем пользователя, если его ещё нет
        queues[chat_id].append(user)
        save_data(queues, last_queue_message)  # Сохраняем изменения

# Удаление пользователя из очереди
def remove_from_queue(chat_id, user):
    # Удаляем пользователя, если он есть, и сохраняем
    queues.get(chat_id, []).remove(user) if user in queues.get(chat_id, []) else None
    save_data(queues, last_queue_message)

# Получить очередь по chat_id
def get_queue(chat_id):
    return queues.get(chat_id, [])

# Получить ID последнего отправленного ботом сообщения об очереди
def get_last_message_id(chat_id):
    return last_queue_message.get(chat_id)

# Установить ID последнего сообщения и сохранить изменения
def set_last_message_id(chat_id, msg_id):
    last_queue_message[chat_id] = msg_id
    save_data(queues, last_queue_message)

# Сформировать текст очереди для отображения
def get_queue_message(chat_id):
    q = get_queue(chat_id)
    text = "\n".join(f"{i + 1}. {u}" for i, u in enumerate(q)) if q else "Очередь пуста."
    return text
