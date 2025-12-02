# Быстрый старт с тестами

## Установка

```bash
# Установить все зависимости
pip install -r requirements.txt
```

## Запуск

```bash
# Запустить все тесты
pytest

# С детальным выводом
pytest -vv

# С покрытием кода
pytest --cov=app

# HTML отчёт покрытия
pytest --cov=app --cov-report=html
```

## Структура

```
tests/
├── test_domain_service.py    # 32 теста - бизнес-логика
├── test_presenter.py         # 9 тестов - форматирование
├── test_utils.py             # 16 тестов - утилиты
├── test_service.py           # 20 тестов - сервис
└── test_integration.py       # 7 тестов - интеграция
```

**Всего: 84 теста**

## Примеры

```bash
# Конкретный файл
pytest tests/test_domain_service.py

# Конкретный класс
pytest tests/test_domain_service.py::TestRemoveByPosOrName

# Конкретный тест
pytest tests/test_domain_service.py::TestRemoveByPosOrName::test_remove_by_position

# Быстро (без вывода)
pytest -q

# Останавливаться на первой ошибке
pytest -x
```

See [TESTING.md](TESTING.md) for more details.
