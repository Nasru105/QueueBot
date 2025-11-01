import json
import os

from .logger import logger

# путь к директории "data" в текущей рабочей директории
DATA_DIR = os.path.join(os.getcwd(), "data")
FILE = os.path.join(DATA_DIR, "queue_data.json")


def load_data():
    try:
        if not os.path.exists(FILE):
            return {}
        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при чтении JSON файла: {e}")
        return {}
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных: {e}")
        return {}


def save_data(data):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        # Сначала пишем во временный файл
        temp_file = FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        # Затем безопасно заменяем основной файл
        os.replace(temp_file, FILE)
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {e}")
