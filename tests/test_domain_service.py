"""
Тесты для QueueDomainService — чистой бизнес-логики очередей.
"""

import pytest

from app.queues.domain import QueueDomainService
from app.queues.errors import InvalidPositionError, UserNotFoundError


class TestGenerateQueueName:
    """Тесты генерации имён очередей."""

    def test_generate_first_queue_name(self):
        """Первая очередь должна быть 'Очередь 1'."""
        queues = {}
        name = QueueDomainService.generate_queue_name(queues)
        assert name == "Очередь 1"

    def test_generate_second_queue_name(self):
        """Вторая очередь должна быть 'Очередь 2'."""
        queues = {"Очередь 1": {"queue": ["Alice"]}}
        name = QueueDomainService.generate_queue_name(queues)
        assert name == "Очередь 2"

    def test_generate_with_empty_queue(self):
        """Пустая очередь не считается при генерации имени."""
        queues = {"Очередь 1": {"queue": []}}
        name = QueueDomainService.generate_queue_name(queues)
        assert name == "Очередь 1"

    def test_generate_with_custom_base(self):
        """Можно использовать кастомный базис для имён."""
        queues = {"Queue 1": {"queue": ["Alice"]}}
        name = QueueDomainService.generate_queue_name(queues, base="Queue")
        assert name == "Queue 2"


class TestRemoveByPosOrName:
    """Тесты удаления пользователей из очереди."""

    def test_remove_by_position(self):
        """Удалить пользователя по позиции."""
        queue = ["Alice", "Bob", "Charlie"]
        result = QueueDomainService.remove_by_pos_or_name(queue, ["2"])
        assert result.removed_name == "Bob"
        assert result.position == 2
        assert result.updated_queue == ["Alice", "Charlie"]

    def test_remove_by_name(self):
        """Удалить пользователя по имени."""
        queue = ["Alice", "Bob Johnson", "Charlie"]
        result = QueueDomainService.remove_by_pos_or_name(queue, ["Bob", "Johnson"])
        assert result.removed_name == "Bob Johnson"
        assert result.position == 2
        assert result.updated_queue == ["Alice", "Charlie"]

    def test_remove_first(self):
        """Удалить первого пользователя."""
        queue = ["Alice", "Bob", "Charlie"]
        result = QueueDomainService.remove_by_pos_or_name(queue, ["1"])
        assert result.removed_name == "Alice"
        assert result.position == 1
        assert result.updated_queue == ["Bob", "Charlie"]

    def test_remove_last(self):
        """Удалить последнего пользователя."""
        queue = ["Alice", "Bob", "Charlie"]
        result = QueueDomainService.remove_by_pos_or_name(queue, ["3"])
        assert result.removed_name == "Charlie"
        assert result.position == 3
        assert result.updated_queue == ["Alice", "Bob"]

    def test_remove_single_user(self):
        """Удалить единственного пользователя."""
        queue = ["Alice"]
        result = QueueDomainService.remove_by_pos_or_name(queue, ["1"])
        assert result.removed_name == "Alice"
        assert result.position == 1
        assert result.updated_queue == []

    def test_remove_position_out_of_range(self):
        """Позиция вне диапазона вызывает ошибку."""
        queue = ["Alice", "Bob"]
        with pytest.raises(InvalidPositionError):
            QueueDomainService.remove_by_pos_or_name(queue, ["5"])

    def test_remove_negative_position(self):
        """Отрицательная позиция вызывает ошибку."""
        queue = ["Alice", "Bob"]
        with pytest.raises(InvalidPositionError):
            QueueDomainService.remove_by_pos_or_name(queue, ["0"])

    def test_remove_nonexistent_user(self):
        """Удаление несуществующего пользователя вызывает ошибку."""
        queue = ["Alice", "Bob"]
        with pytest.raises(UserNotFoundError):
            QueueDomainService.remove_by_pos_or_name(queue, ["Charlie"])

    def test_remove_from_empty_queue(self):
        """Удаление из пустой очереди."""
        queue = None
        result = QueueDomainService.remove_by_pos_or_name(queue, ["1"])
        assert result.removed_name is None
        assert result.position is None
        assert result.updated_queue is None


class TestInsertAtPosition:
    """Тесты вставки пользователей в очередь."""

    def test_insert_at_end(self):
        """Вставить пользователя в конец (по умолчанию)."""
        queue = ["Alice", "Bob"]
        result = QueueDomainService.insert_at_position(queue, "Charlie", None)
        assert result.user_name == "Charlie"
        assert result.position == 3
        assert result.updated_queue == ["Alice", "Bob", "Charlie"]
        assert result.old_position is None

    def test_insert_at_beginning(self):
        """Вставить пользователя в начало."""
        queue = ["Alice", "Bob"]
        result = QueueDomainService.insert_at_position(queue, "Charlie", 0)
        assert result.user_name == "Charlie"
        assert result.position == 1
        assert result.updated_queue == ["Charlie", "Alice", "Bob"]

    def test_insert_in_middle(self):
        """Вставить пользователя в середину."""
        queue = ["Alice", "Charlie"]
        result = QueueDomainService.insert_at_position(queue, "Bob", 1)
        assert result.user_name == "Bob"
        assert result.position == 2
        assert result.updated_queue == ["Alice", "Bob", "Charlie"]

    def test_insert_into_empty_queue(self):
        """Вставить в пустую очередь."""
        queue = []
        result = QueueDomainService.insert_at_position(queue, "Alice", None)
        assert result.user_name == "Alice"
        assert result.position == 1
        assert result.updated_queue == ["Alice"]

    def test_insert_existing_user_moves(self):
        """Существующий пользователь переместится."""
        queue = ["Alice", "Bob", "Charlie"]
        result = QueueDomainService.insert_at_position(queue, "Bob", 0)
        assert result.user_name == "Bob"
        assert result.position == 1
        assert result.old_position == 2  # был на позиции 2
        assert result.updated_queue == ["Bob", "Alice", "Charlie"]

    def test_insert_position_out_of_bounds(self):
        """Позиция вне допустимого диапазона."""
        queue = ["Alice", "Bob"]
        with pytest.raises(InvalidPositionError):
            QueueDomainService.insert_at_position(queue, "Charlie", 5)

    def test_insert_negative_position(self):
        """Отрицательная позиция вызывает ошибку."""
        queue = ["Alice"]
        with pytest.raises(InvalidPositionError):
            QueueDomainService.insert_at_position(queue, "Bob", -1)

    def test_insert_into_none_queue(self):
        """Вставка в None."""
        result = QueueDomainService.insert_at_position(None, "Alice", None)
        assert result.user_name is None


class TestReplaceByPositions:
    """Тесты замены пользователей по позициям."""

    def test_replace_two_positions(self):
        """Поменять пользователей на двух позициях."""
        queue = ["Alice", "Bob", "Charlie"]
        result = QueueDomainService.replace_by_positions(queue, 0, 2, "test_queue")
        assert result.user1 == "Alice"
        assert result.user2 == "Charlie"
        assert result.pos1 == 0
        assert result.pos2 == 2
        assert result.updated_queue == ["Charlie", "Bob", "Alice"]

    def test_replace_adjacent_positions(self):
        """Поменять соседних пользователей."""
        queue = ["Alice", "Bob", "Charlie"]
        result = QueueDomainService.replace_by_positions(queue, 0, 1, "test_queue")
        assert result.updated_queue == ["Bob", "Alice", "Charlie"]

    def test_replace_same_positions_error(self):
        """Замена одинаковых позиций вызывает ошибку."""
        queue = ["Alice", "Bob"]
        with pytest.raises(InvalidPositionError):
            QueueDomainService.replace_by_positions(queue, 0, 0, "test_queue")

    def test_replace_out_of_bounds(self):
        """Позиция вне диапазона."""
        queue = ["Alice", "Bob"]
        with pytest.raises(InvalidPositionError):
            QueueDomainService.replace_by_positions(queue, 0, 5, "test_queue")


class TestReplaceByNames:
    """Тесты замены пользователей по именам."""

    def test_replace_two_names(self):
        """Поменять пользователей по имёнам."""
        queue = ["Alice", "Bob Johnson", "Charlie"]
        result = QueueDomainService.replace_by_names(queue, "Alice", "Charlie", "test_queue")
        assert result.user1 == "Alice"
        assert result.user2 == "Charlie"
        assert result.updated_queue == ["Charlie", "Bob Johnson", "Alice"]

    def test_replace_nonexistent_name(self):
        """Замена несуществующего пользователя."""
        queue = ["Alice", "Bob"]
        with pytest.raises(UserNotFoundError):
            QueueDomainService.replace_by_names(queue, "Alice", "David", "test_queue")
