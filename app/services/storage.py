import json
import os

# путь к директории "data" в текущей рабочей директории
DATA_DIR = os.path.join(os.getcwd(), "data")
FILE = os.path.join(DATA_DIR, "queue_data.json")


def load_data():
    if not os.path.exists(FILE):
        return {}
    with open(FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
