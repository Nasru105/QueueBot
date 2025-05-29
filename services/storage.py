import json  # Импортируем модуль json для работы с JSON-файлами (сериализация/десериализация данных)
import os  # Импортируем os для проверки существования файла

# Название файла, в котором будет храниться информация об очередях
FILE = "queue_data.json"


# Функция для загрузки данных из файла
def load_data():
    # Если файл не существует, возвращаем пустые словари
    if not os.path.exists(FILE):
        return {}, {}

    # Открываем файл и загружаем содержимое
    with open(FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        # Возвращаем данные из файла: очередь и последние ID сообщений
        return data.get("queues", {}), data.get("last_queue_message", {})


# Функция для сохранения данных в файл
def save_data(queues, last_queue_message):
    # Открываем файл на запись и сохраняем данные в формате JSON
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump({
            "queues": queues,
            "last_queue_message": last_queue_message
        }, f, ensure_ascii=False,
            indent=2)  # ensure_ascii=False позволяет сохранить кириллицу, indent=2 — форматирование
