import json  # Импортируем модуль json для работы с JSON-файлами (сериализация/десериализация данных)
import os  # Импортируем os для проверки существования файла

# Путь к файлу в Volume
FILE = "/data/queue_data.json"

def load_data():
    if not os.path.exists(FILE):
        return {}, {}
    with open(FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("queues", {}), data.get("last_queue_message", {})

def save_data(queues, last_queue_message):
    os.makedirs(os.path.dirname(FILE), exist_ok=True)  # Создать директорию, если её нет
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump({"queues": queues, "last_queue_message": last_queue_message}, f)


