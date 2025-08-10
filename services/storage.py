import json
import os

# Путь к файлу в папке проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # директория, где лежит текущий скрипт
FILE = os.path.join(BASE_DIR, "queue_data.json")  # файл будет рядом со скриптом


def load_data():
    if not os.path.exists(FILE):
        return {}, {}
    with open(FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("queues", {}), data.get("last_queue_message", {})


def save_data(queues, last_queue_message):
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"queues": queues, "last_queue_message": last_queue_message},
            f,
            ensure_ascii=False,  #  ключ, чтобы писать символы как есть
            indent=4,  #  красиво форматируем
        )
