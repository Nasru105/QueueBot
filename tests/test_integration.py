"""
Интеграционные тесты для сценариев работы.
"""

from app.queues.domain import QueueDomainService
from app.queues.presenter import QueuePresenter


class TestQueueWorkflow:
    """Интеграционные тесты полного цикла работы с очередью."""

    def test_queue_creation_and_user_management(self):
        """Сценарий: создание очереди и управление пользователями."""
        # Имитируем очередь
        queue = []

        # 1. Добавляем пользователей
        queue.extend(["Alice", "Bob", "Charlie"])
        assert len(queue) == 3

        # 2. Формируем текст очереди
        presenter = QueuePresenter()
        text = presenter.format_queue_text("Meeting", queue)
        assert "Meeting" in text
        assert "Alice" in text
        assert "1\\. Alice" in text
        assert "3\\. Charlie" in text

        # 3. Удаляем пользователя
        result = QueueDomainService.remove_by_pos_or_name(queue, ["2"])
        assert result.removed_name == "Bob"
        queue = result.updated_queue

        # 4. Обновляем текст
        text = presenter.format_queue_text("Meeting", queue)
        assert "Bob" not in text
        assert "Alice" in text

    def test_queue_with_user_movement(self):
        """Сценарий: перемещение пользователя в очереди."""
        queue = ["Alice", "Bob", "Charlie"]

        # 1. Перемещаем Bob в начало
        result = QueueDomainService.insert_at_position(queue, "Bob", 0)
        queue = result.updated_queue
        assert queue[0] == "Bob"
        assert result.old_position == 2

        # 2. Перемещаем Alice в конец
        result = QueueDomainService.insert_at_position(queue, "Alice", None)
        queue = result.updated_queue
        assert queue[-1] == "Alice"

    def test_queue_replacement_workflow(self):
        """Сценарий: замена пользователей в очереди."""
        queue = ["Alice", "Bob", "Charlie", "David"]

        # Заменяем Alice и David
        result = QueueDomainService.replace_by_names(queue, "Alice", "David", "test_queue")
        queue = result.updated_queue
        assert queue[0] == "David"
        assert queue[3] == "Alice"

        # Заменяем по позициям
        result = QueueDomainService.replace_by_positions(queue, 1, 2, "test_queue")
        queue = result.updated_queue
        assert queue[1] == "Charlie"
        assert queue[2] == "Bob"

    def test_multiple_operations_sequence(self):
        """Сценарий: последовательность разных операций."""
        queue = []

        # 1. Добавляем пользователей
        for user in ["Alice", "Bob", "Charlie", "David", "Eve"]:
            result = QueueDomainService.insert_at_position(queue, user, None)
            queue = result.updated_queue

        assert len(queue) == 5

        # 2. Удаляем второго
        result = QueueDomainService.remove_by_pos_or_name(queue, ["2"])
        queue = result.updated_queue
        assert "Bob" not in queue

        # 3. Вставляем нового в позицию 2
        result = QueueDomainService.insert_at_position(queue, "Frank", 1)
        queue = result.updated_queue
        assert queue[1] == "Frank"

        # 4. Проверяем, что всё в порядке
        presenter = QueuePresenter()
        text = presenter.format_queue_text("Queue", queue)
        assert "Frank" in text
        assert "Bob" not in text
        assert len(queue) == 5


class TestEdgeCases:
    """Тесты граничных случаев."""

    def test_single_user_queue_operations(self):
        """Операции с очередью из одного пользователя."""
        queue = ["Alice"]

        # Удаление
        result = QueueDomainService.remove_by_pos_or_name(queue, ["1"])
        assert result.removed_name == "Alice"
        assert result.updated_queue == []

        # Вставка в пустую
        queue = []
        result = QueueDomainService.insert_at_position(queue, "Alice", None)
        assert len(result.updated_queue) == 1

    def test_queue_with_similar_names(self):
        """Очередь с похожими именами."""
        queue = ["Alice", "Alice Smith", "Alice Johnson"]

        # Должна найтись точная позиция
        result = QueueDomainService.remove_by_pos_or_name(queue, ["Alice"])
        assert result.removed_name == "Alice"
        assert "Alice Smith" in result.updated_queue

    def test_empty_queue_operations(self):
        """Операции с пустой очередью."""
        queue = None

        result = QueueDomainService.insert_at_position(queue, "Alice", None)
        assert result.user_name is None

        result = QueueDomainService.remove_by_pos_or_name(queue, ["1"])
        assert result.removed_name is None
