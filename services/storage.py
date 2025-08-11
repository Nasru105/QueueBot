import json
import os

# Получаем путь к корню проекта (на 2 уровня выше от storage.py)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".", ".."))

DATA_DIR = os.path.join(BASE_DIR, "data")
FILE = os.path.join(DATA_DIR, "queue_data.json")


def load_data():
    if not os.path.exists(FILE):
        return {}
    with open(FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4,
        )

