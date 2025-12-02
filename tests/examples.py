"""
Руководство по написанию новых тестов для QueueBot.

Этот файл содержит примеры и лучшие практики.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# ============================================================================
# ПРИМЕР 1: Простой unit тест
# ============================================================================


def test_simple_calculation():
    """Пример простого теста без зависимостей."""
    result = 2 + 2
    assert result == 4
    assert result != 5


# ============================================================================
# ПРИМЕР 2: Тест с фикстурой
# ============================================================================


@pytest.fixture
def sample_queue():
    """Фикстура: готовая очередь для тестов."""
    return ["Alice", "Bob", "Charlie"]


def test_with_fixture(sample_queue):
    """Использование фикстуры."""
    assert len(sample_queue) == 3
    assert "Alice" in sample_queue
    assert sample_queue[0] == "Alice"


# ============================================================================
# ПРИМЕР 3: Параметризованные тесты
# ============================================================================


@pytest.mark.parametrize(
    "input_pos,expected_name",
    [
        (1, "Alice"),
        (2, "Bob"),
        (3, "Charlie"),
    ],
)
def test_position_mapping(input_pos, expected_name, sample_queue):
    """Одного теста для разных входных данных."""
    assert sample_queue[input_pos - 1] == expected_name


# ============================================================================
# ПРИМЕР 4: Тест с AsyncMock (async операции)
# ============================================================================


@pytest.fixture
def mock_repository():
    """Фикстура: мок репозитория."""
    repo = AsyncMock()
    repo.get_queue = AsyncMock()
    repo.update_queue = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_async_operation(mock_repository):
    """Пример тестирования async функции."""
    mock_repository.get_queue.return_value = ["Alice", "Bob"]

    result = await mock_repository.get_queue(123, "Queue 1")

    assert result == ["Alice", "Bob"]
    mock_repository.get_queue.assert_called_once_with(123, "Queue 1")


# ============================================================================
# ПРИМЕР 5: Тест с проверкой исключений
# ============================================================================

from app.queues.errors import InvalidPositionError


def test_exception_raising():
    """Проверка, что функция выбрасывает исключение."""
    from app.queues.domain import QueueDomainService

    queue = ["Alice", "Bob"]

    # Проверяем, что выбрасывается исключение
    with pytest.raises(InvalidPositionError):
        QueueDomainService.remove_by_pos_or_name(queue, ["10"])


# ============================================================================
# ПРИМЕР 6: Тест с моком и проверкой вызовов
# ============================================================================


@pytest.mark.asyncio
async def test_mock_calls():
    """Проверка, что функция вызывает правильные методы."""
    mock_logger = MagicMock()
    mock_repo = AsyncMock()

    # Настраиваем моки
    mock_repo.create_queue = AsyncMock()

    # Тестируемое действие
    await mock_repo.create_queue(123, "Chat", "Queue")

    # Проверяем вызовы
    mock_repo.create_queue.assert_called_once_with(123, "Chat", "Queue")
    assert mock_repo.create_queue.call_count == 1


# ============================================================================
# ПРИМЕР 7: Класс для группировки тестов
# ============================================================================


class TestQueueOperations:
    """Группировка связанных тестов в класс."""

    def test_add_to_empty_queue(self):
        """Добавить в пустую очередь."""
        queue = []
        queue.append("Alice")
        assert len(queue) == 1

    def test_add_to_non_empty_queue(self):
        """Добавить в непустую очередь."""
        queue = ["Alice"]
        queue.append("Bob")
        assert len(queue) == 2
        assert queue[-1] == "Bob"


# ============================================================================
# ПРИМЕР 8: Использование context manager
# ============================================================================


def test_with_context_manager():
    """Пример с context manager (pytest.raises)."""
    from app.queues.errors import InvalidPositionError

    with pytest.raises(InvalidPositionError) as exc_info:
        raise InvalidPositionError("Out of range")

    assert "Out of range" in str(exc_info.value)


# ============================================================================
# ПРИМЕР 9: Тест с несколькими проверками
# ============================================================================


def test_multiple_assertions():
    """Тест с несколькими проверками."""
    from app.queues.domain import QueueDomainService

    queue = ["Alice", "Bob", "Charlie"]
    result = QueueDomainService.remove_by_pos_or_name(queue, ["2"])

    # Несколько проверок в одном тесте
    assert result.removed_name == "Bob"
    assert result.position == 2
    assert result.updated_queue == ["Alice", "Charlie"]
    assert len(result.updated_queue) == 2


# ============================================================================
# ПРИМЕР 10: Тест с фикстурой с setup/teardown
# ============================================================================


@pytest.fixture(autouse=True)
def cleanup():
    """Фикстура с очисткой после теста."""
    # Setup (перед тестом)
    print("Начало теста")

    yield  # Здесь выполняется сам тест

    # Teardown (после теста)
    print("Конец теста")


def test_with_cleanup(cleanup):
    """Тест, который использует cleanup."""
    assert True


# ============================================================================
# РЕКОМЕНДАЦИИ
# ============================================================================

"""
1. ИМЕНОВАНИЕ ТЕСТОВ:
   - Начинайте с "test_"
   - Используйте описательные имена на английском: test_remove_by_position
   - На русском в docstring: "Удаление по позиции"

2. СТРУКТУРА ТЕСТА (Arrange-Act-Assert):
   def test_something():
       # Arrange - подготовка данных
       queue = ["Alice", "Bob"]
       
       # Act - выполнение
       result = process(queue)
       
       # Assert - проверка
       assert result.success

3. ФИКСТУРЫ:
   - Используйте для общих данных
   - Называйте понятно (sample_queue, mock_repo)
   - Используйте autouse=True если нужны для всех тестов

4. ПАРАМЕТРИЗАЦИЯ:
   - Вместо копирования логики теста используйте @pytest.mark.parametrize
   - Минимизирует дублирование кода

5. ASYNC ТЕСТЫ:
   - Используйте @pytest.mark.asyncio
   - Используйте AsyncMock для async операций
   - Не забывайте await

6. МОКИ:
   - Используйте AsyncMock для async методов
   - Используйте MagicMock для обычных методов
   - Проверяйте вызовы: assert_called_once_with()

7. ИСКЛЮЧЕНИЯ:
   - Проверяйте с pytest.raises()
   - Используйте as exc_info для проверки сообщения

8. ГРАНИЧНЫЕ СЛУЧАИ:
   - Пустые списки, None значения
   - Максимальные/минимальные значения
   - Некорректные входные данные

9. ЧИТАЕМОСТЬ:
   - Один assert на тест (если возможно)
   - Понятные имена переменных
   - Русские комментарии для объяснения

10. ОРГАНИЗАЦИЯ:
    - Группируйте тесты в классы
    - По одному тесту на сценарий
    - Следуйте структуре компонентов
"""

# ============================================================================
# ЗАПУСК ПРИМЕРОВ
# ============================================================================

"""
Запустите примеры:
    pytest examples.py -v

Запустите конкретный пример:
    pytest examples.py::test_simple_calculation -v

Запустите класс примеров:
    pytest examples.py::TestQueueOperations -v
"""
