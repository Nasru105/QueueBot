"""
Тесты для моделей Queue - бизнес-логики работы с очередью.
"""

import pytest

from app.queues.errors import InvalidPositionError, MembersNotFoundError, UserNotFoundError
from app.queues.models import Member, Queue


@pytest.fixture
def sample_queue():
    """Пример очереди с пользователями."""
    return Queue(
        id="test_queue",
        name="Test Queue",
        members=[
            Member(user_id=1, display_name="Alice"),
            Member(user_id=2, display_name="Bob"),
            Member(user_id=3, display_name="Charlie"),
        ],
    )


class TestInsert:
    """Тесты для вставки пользователей в очередь."""

    def test_insert_at_end(self, sample_queue):
        """Вставка в конец очереди."""
        old_pos, new_pos = sample_queue.insert("Diana", user_id=4)
        assert new_pos == 4
        assert old_pos is None
        assert len(sample_queue.members) == 4
        assert sample_queue.members[-1].display_name == "Diana"

    def test_insert_at_specific_position(self, sample_queue):
        """Вставка в конкретную позицию."""
        old_pos, new_pos = sample_queue.insert("Diana", desired_pos=1, user_id=4)
        assert new_pos == 2
        assert old_pos is None
        assert sample_queue.members[1].display_name == "Diana"
        assert len(sample_queue.members) == 4

    def test_insert_at_beginning(self, sample_queue):
        """Вставка в начало очереди."""
        old_pos, new_pos = sample_queue.insert("Diana", desired_pos=0, user_id=4)
        assert new_pos == 1
        assert old_pos is None
        assert len(sample_queue.members) == 4
        assert sample_queue.members[0].display_name == "Diana"

    def test_insert_duplicate_user(self, sample_queue):
        """Повторная вставка существующего пользователя - перемещение."""
        old_pos, new_pos = sample_queue.insert("Bob", desired_pos=0)
        assert new_pos == 1
        assert old_pos == 2
        assert len(sample_queue.members) == 3
        assert sample_queue.members[0].display_name == "Bob"

    def test_insert_position_out_of_bounds_max(self, sample_queue):
        """Вставка с позицией больше размера - должна вставить в конец."""
        old_pos, new_pos = sample_queue.insert("Diana", desired_pos=100, user_id=4)
        assert new_pos == 4
        assert old_pos is None
        assert sample_queue.members[-1].display_name == "Diana"

    def test_insert_position_negative(self, sample_queue):
        """Отрицательная позиция - вставка в начало."""
        old_pos, new_pos = sample_queue.insert("Diana", desired_pos=-10, user_id=4)
        assert new_pos == 1
        assert sample_queue.members[0].display_name == "Diana"


class TestRemove:
    """Тесты для удаления из очереди."""

    def test_remove_by_name_success(self, sample_queue):
        """Удаление по имени пользователя."""
        removed_name, pos = sample_queue.remove("Bob")
        assert removed_name == "Bob"
        assert pos == 2
        assert len(sample_queue.members) == 2

    def test_remove_by_name_not_found(self, sample_queue):
        """Ошибка при удалении несуществующего пользователя."""
        with pytest.raises(UserNotFoundError):
            sample_queue.remove("Unknown")

    def test_remove_by_name_multiword(self):
        """Удаление по имени из нескольких слов."""
        queue = Queue(
            id="q1",
            name="Test Queue",
            members=[
                Member(user_id=1, display_name="John Doe"),
                Member(user_id=2, display_name="Jane Smith"),
            ],
        )
        removed_name, pos = queue.remove("John Doe")
        assert removed_name == "John Doe"
        assert pos == 1

    def test_remove_from_empty_queue(self):
        """Ошибка при удалении из пустой очереди."""
        queue = Queue(id="q1", name="Test Queue", members=[])
        with pytest.raises(MembersNotFoundError):
            queue.remove("Alice")


class TestRemoveByPosition:
    """Тесты для удаления из очереди по позиции."""

    def test_pop_from_end(self, sample_queue):
        """Удаление последнего пользователя (по умолчанию)."""
        removed_name, pos = sample_queue.pop(2)
        assert removed_name == "Charlie"
        assert pos == 3
        assert len(sample_queue.members) == 2

    def test_pop_at_specific_position(self, sample_queue):
        """Удаление по конкретной позиции (0-индекс)."""
        removed_name, pos = sample_queue.pop(0)
        assert removed_name == "Alice"
        assert pos == 1
        assert len(sample_queue.members) == 2

    def test_pop_from_middle(self, sample_queue):
        """Удаление из середины очереди."""
        removed_name, pos = sample_queue.pop(1)
        assert removed_name == "Bob"
        assert pos == 2
        assert len(sample_queue.members) == 2

    def test_pop_invalid_position(self, sample_queue):
        """Ошибка при удалении с невалидной позицией."""
        with pytest.raises(InvalidPositionError):
            sample_queue.pop(10)

    def test_pop_from_empty_queue(self):
        """Ошибка при удалении из пустой очереди."""
        queue = Queue(id="q1", name="Test Queue", members=[])
        with pytest.raises(MembersNotFoundError):
            queue.pop()


class TestReplaceByPositions:
    """Тесты для обмена пользователей местами."""

    def test_swap_valid_positions(self, sample_queue):
        """Обмен двух пользователей местами."""
        pos1, pos2, name1, name2 = sample_queue.swap_by_position(0, 2)
        assert name1 == "Alice"
        assert name2 == "Charlie"
        assert pos1 == 1
        assert pos2 == 3
        assert sample_queue.members[0].display_name == "Charlie"
        assert sample_queue.members[2].display_name == "Alice"

    def test_swap_adjacent_positions(self, sample_queue):
        """Обмен соседних пользователей."""
        pos1, pos2, name1, name2 = sample_queue.swap_by_position(0, 1)
        assert sample_queue.members[0].display_name == "Bob"
        assert sample_queue.members[1].display_name == "Alice"

    def test_swap_same_positions_error(self, sample_queue):
        """Ошибка при одинаковых позициях."""
        with pytest.raises(InvalidPositionError):
            sample_queue.swap_by_position(0, 0)

    def test_swap_invalid_pos1(self, sample_queue):
        """Ошибка при невалидной первой позиции."""
        with pytest.raises(InvalidPositionError):
            sample_queue.swap_by_position(-1, 1)

    def test_swap_invalid_pos2(self, sample_queue):
        """Ошибка при невалидной второй позиции."""
        with pytest.raises(InvalidPositionError):
            sample_queue.swap_by_position(0, 10)


class TestReplaceByNames:
    """Тесты для обмена по именам пользователей."""

    def test_swap_by_names_success(self, sample_queue):
        """Успешный обмен по именам."""
        pos1, pos2, name1, name2 = sample_queue.swap_by_name("Alice", "Charlie")
        assert name1 == "Alice"
        assert name2 == "Charlie"
        assert sample_queue.members[0].display_name == "Charlie"
        assert sample_queue.members[2].display_name == "Alice"

    def test_swap_by_names_adjacent(self, sample_queue):
        """Обмен соседних пользователей по именам."""
        pos1, pos2, name1, name2 = sample_queue.swap_by_name("Alice", "Bob")
        assert sample_queue.members[0].display_name == "Bob"
        assert sample_queue.members[1].display_name == "Alice"

    def test_swap_by_names_first_not_found(self, sample_queue):
        """Ошибка если первого пользователя нет."""
        with pytest.raises(UserNotFoundError):
            sample_queue.swap_by_name("Unknown", "Alice")

    def test_swap_by_names_second_not_found(self, sample_queue):
        """Ошибка если второго пользователя нет."""
        with pytest.raises(UserNotFoundError):
            sample_queue.swap_by_name("Alice", "Unknown")

    def test_swap_by_names_both_not_found(self, sample_queue):
        """Ошибка если обоих пользователей нет."""
        with pytest.raises(UserNotFoundError):
            sample_queue.swap_by_name("Unknown1", "Unknown2")

    def test_swap_by_names_multiword_names(self):
        """Обмен с многословными именами."""
        queue = Queue(
            id="q1",
            name="Test Queue",
            members=[
                Member(user_id=1, display_name="John Doe"),
                Member(user_id=2, display_name="Jane Smith"),
                Member(user_id=3, display_name="Bob Johnson"),
            ],
        )
        pos1, pos2, name1, name2 = queue.swap_by_name("John Doe", "Bob Johnson")
        assert queue.members[0].display_name == "Bob Johnson"
        assert queue.members[2].display_name == "John Doe"


class TestComplexScenarios:
    """Тесты для сложных сценариев работы с очередью."""

    def test_remove_and_insert_sequence(self, sample_queue):
        """Последовательность удаления и вставки."""
        # Удаляем Bob
        removed_name, position = sample_queue.remove("Bob")
        assert removed_name == "Bob"
        assert position == 2
        assert len(sample_queue.members) == 2

        # Вставляем его в начало
        old_pos, new_pos = sample_queue.insert("Bob", desired_pos=0, user_id=2)
        assert new_pos == 1
        assert sample_queue.members[0].display_name == "Bob"

    def test_multiple_swaps(self):
        """Несколько замен подряд."""
        queue = Queue(
            id="q1",
            name="Test Queue",
            members=[
                Member(user_id=1, display_name="Alice"),
                Member(user_id=2, display_name="Bob"),
                Member(user_id=3, display_name="Charlie"),
                Member(user_id=4, display_name="Diana"),
            ],
        )

        # Меняем Alice и Bob
        pos1, pos2, name1, name2 = queue.swap_by_position(0, 1)
        assert queue.members[0].display_name == "Bob"
        assert queue.members[1].display_name == "Alice"

        # Меняем Charlie и Diana
        pos1, pos2, name1, name2 = queue.swap_by_position(2, 3)
        assert queue.members[2].display_name == "Diana"
        assert queue.members[3].display_name == "Charlie"

    def test_insert_with_duplicate_then_remove(self):
        """Вставка дубликата и затем удаление."""
        queue = Queue(
            id="q1",
            name="Test Queue",
            members=[
                Member(user_id=1, display_name="Alice"),
                Member(user_id=2, display_name="Bob"),
            ],
        )

        # Вставляем Alice в начало (она переместится)
        old_pos, new_pos = queue.insert("Alice", desired_pos=0)
        assert old_pos == 1  # была на позиции 1
        assert new_pos == 1  # теперь на позиции 1
        assert len(queue.members) == 2

        # Теперь удаляем Alice
        removed_name, position = queue.remove("Alice")
        assert removed_name == "Alice"
        assert len(queue.members) == 1
        assert queue.members[0].display_name == "Bob"
