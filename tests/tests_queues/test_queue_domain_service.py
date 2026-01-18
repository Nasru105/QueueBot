"""
Тесты для QueueDomainService - чистой бизнес-логики работы с очередью.
"""

import pytest

from app.queues.domain import QueueDomainService
from app.queues.errors import InvalidPositionError, MembersNotFoundError, UserNotFoundError


@pytest.fixture
def domain_service():
    """Фикстура для создания экземпляра сервиса."""
    return QueueDomainService()


@pytest.fixture
def sample_members():
    """Пример очереди с пользователями."""
    return [
        {"user_id": 1, "display_name": "Alice"},
        {"user_id": 2, "display_name": "Bob"},
        {"user_id": 3, "display_name": "Charlie"},
    ]


class TestGenerateQueueName:
    """Тесты для генерации имён очередей."""

    def test_generate_queue_name_empty_dict(self, domain_service: QueueDomainService):
        """Должна вернуть 'Очередь 1' для пустого словаря."""
        result = domain_service.generate_queue_name({})
        assert result == "Очередь 1"

    def test_generate_queue_name_with_existing(self, domain_service: QueueDomainService):
        """Должна вернуть следующее свободное имя."""
        queues = {
            "queue_1": {"name": "Очередь 1", "members": [1, 2]},
            "queue_2": {"name": "Очередь 2", "members": [3, 4]},
        }
        result = domain_service.generate_queue_name(queues)
        assert result == "Очередь 3"

    def test_generate_queue_name_with_custom_base(self, domain_service: QueueDomainService):
        """Должна использовать кастомное базовое имя."""
        queues = {"queue_1": {"name": "Спортзал 1", "members": [1, 2]}}
        result = domain_service.generate_queue_name(queues, base="Спортзал")
        assert result == "Спортзал 2"

    def test_generate_queue_name_with_gaps(self, domain_service: QueueDomainService):
        """Должна найти первую доступную позицию."""
        queues = {
            "queue_1": {"name": "Очередь 1", "members": [1]},
            "queue_3": {"name": "Очередь 3", "members": [2]},
        }
        result = domain_service.generate_queue_name(queues)
        assert result == "Очередь 2"


class TestRemoveByName:
    """Тесты для удаления из очереди по имени."""

    def test_remove_by_name_success(self, domain_service: QueueDomainService, sample_members):
        """Удаление по имени пользователя."""
        removed_name, pos = domain_service.remove_by_name(sample_members, "Bob")
        assert removed_name == "Bob"
        assert pos == 2
        assert len(sample_members) == 2

    def test_remove_by_name_not_found(self, domain_service: QueueDomainService, sample_members):
        """Ошибка при удалении несуществующего пользователя."""
        with pytest.raises(UserNotFoundError):
            domain_service.remove_by_name(sample_members, "Unknown")

    def test_remove_by_name_multiword(self, domain_service: QueueDomainService):
        """Удаление по имени из нескольких слов."""
        queue = [
            {"user_id": 1, "display_name": "John Doe"},
            {"user_id": 2, "display_name": "Jane Smith"},
        ]
        removed_name, pos = domain_service.remove_by_name(queue, "John Doe")
        assert removed_name == "John Doe"
        assert pos == 1

    def test_remove_from_empty_queue(self, domain_service: QueueDomainService):
        """Ошибка при удалении из пустой очереди."""
        with pytest.raises(UserNotFoundError):
            domain_service.remove_by_name([], "Alice")

    def test_remove_from_none_queue(self, domain_service: QueueDomainService):
        """Обработка None в качестве очереди."""
        with pytest.raises(MembersNotFoundError):
            domain_service.remove_by_name(None, "Alice")


class TestRemoveByPos:
    """Тесты для удаления из очереди по позиции."""

    def test_remove_by_position_success(self, domain_service: QueueDomainService, sample_members):
        """Удаление по валидной позиции."""
        removed_name, pos = domain_service.remove_by_position(sample_members, 2)
        assert removed_name == "Bob"
        assert pos == 2
        assert len(sample_members) == 2
        assert sample_members[0]["display_name"] == "Alice"
        assert sample_members[1]["display_name"] == "Charlie"

    def test_remove_by_position_first(self, domain_service: QueueDomainService, sample_members):
        """Удаление первого пользователя."""
        removed_name, pos = domain_service.remove_by_position(sample_members, 1)
        assert removed_name == "Alice"
        assert pos == 1
        assert len(sample_members) == 2

    def test_remove_by_position_last(self, domain_service: QueueDomainService, sample_members):
        """Удаление последнего пользователя."""
        removed_name, pos = domain_service.remove_by_position(sample_members, 3)
        assert removed_name == "Charlie"
        assert pos == 3

    def test_remove_by_position_invalid(self, domain_service: QueueDomainService, sample_members):
        """Ошибка при удалении с невалидной позицией."""
        with pytest.raises(InvalidPositionError):
            domain_service.remove_by_position(sample_members, 10)

    def test_remove_by_position_zero(self, domain_service: QueueDomainService, sample_members):
        """Ошибка при позиции 0."""
        with pytest.raises(InvalidPositionError):
            domain_service.remove_by_position(sample_members, 0)

    def test_remove_from_empty_queue(self, domain_service: QueueDomainService):
        """Ошибка при удалении из пустой очереди."""
        with pytest.raises(InvalidPositionError):
            domain_service.remove_by_position([], 1)

    def test_remove_from_none_queue(self, domain_service: QueueDomainService):
        """Обработка None в качестве очереди."""
        with pytest.raises(MembersNotFoundError):
            domain_service.remove_by_position(None, 1)


class TestInsertAtPosition:
    """Тесты для вставки пользователей в очередь."""

    def test_insert_at_end(self, domain_service: QueueDomainService, sample_members):
        """Вставка в конец очереди."""
        user_name, desired_pos, old_position = domain_service.insert_at_position(sample_members, "Diana", None)
        assert user_name == "Diana"
        assert desired_pos == 4
        assert old_position is None
        assert len(sample_members) == 4
        assert sample_members[-1]["display_name"] == "Diana"

    def test_insert_at_specific_position(self, domain_service: QueueDomainService, sample_members):
        """Вставка в конкретную позицию."""
        user_name, desired_pos, old_position = domain_service.insert_at_position(sample_members, "Diana", 1)
        assert user_name == "Diana"
        assert desired_pos == 2
        assert old_position is None
        assert sample_members[1]["display_name"] == "Diana"
        assert len(sample_members) == 4

    def test_insert_at_beginning(self, domain_service: QueueDomainService, sample_members):
        """Вставка в начало очереди."""
        user_name, desired_pos, old_position = domain_service.insert_at_position(sample_members, "Diana", 0)
        assert desired_pos == 1
        assert user_name == "Diana"
        assert old_position is None
        assert len(sample_members) == 4
        assert sample_members[0]["display_name"] == "Diana"

    def test_insert_duplicate_user(self, domain_service: QueueDomainService, sample_members):
        """Повторная вставка существующего пользователя - перемещение."""
        user_name, desired_pos, old_position = domain_service.insert_at_position(sample_members, "Bob", 0)
        assert user_name == "Bob"
        assert desired_pos == 1
        assert old_position == 2
        assert len(sample_members) == 3
        assert sample_members[0]["display_name"] == "Bob"

    def test_insert_position_out_of_bounds_max(self, domain_service: QueueDomainService, sample_members):
        """Вставка с позицией больше размера - должна вставить в конец."""
        user_name, desired_pos, old_position = domain_service.insert_at_position(sample_members, "Diana", 100)
        assert user_name == "Diana"
        assert desired_pos == 4
        assert old_position is None
        assert sample_members[-1]["display_name"] == "Diana"

    def test_insert_position_negative(self, domain_service: QueueDomainService, sample_members):
        """Отрицательная позиция - вставка в начало."""
        user_name, desired_pos, old_position = domain_service.insert_at_position(sample_members, "Diana", -10)
        assert desired_pos == 1
        assert sample_members[0]["display_name"] == "Diana"

    def test_insert_into_empty_queue(self, domain_service: QueueDomainService):
        """Вставка в пустую очередь."""
        members = []
        user_name, desired_pos, old_position = domain_service.insert_at_position(members, "Alice", None)
        assert user_name == "Alice"
        assert desired_pos == 1
        assert old_position is None
        assert len(members) == 1

    def test_insert_into_none_queue(self, domain_service: QueueDomainService):
        """Обработка None в качестве очереди."""
        with pytest.raises(MembersNotFoundError):
            domain_service.insert_at_position(None, "Alice", None)


class TestReplaceByPositions:
    """Тесты для обмена пользователей местами."""

    def test_replace_valid_positions(self, domain_service: QueueDomainService, sample_members):
        """Обмен двух пользователей местами."""
        pos1, pos2, name1, name2 = domain_service.replace_by_positions(sample_members, 1, 3)
        assert name1 == "Alice"
        assert name2 == "Charlie"
        assert pos1 == 1
        assert pos2 == 3
        assert sample_members[0]["display_name"] == "Charlie"
        assert sample_members[2]["display_name"] == "Alice"

    def test_replace_adjacent_positions(self, domain_service: QueueDomainService, sample_members):
        """Обмен соседних пользователей."""
        pos1, pos2, name1, name2 = domain_service.replace_by_positions(sample_members, 1, 2)
        assert sample_members[0]["display_name"] == "Bob"
        assert sample_members[1]["display_name"] == "Alice"

    def test_replace_same_positions_error(self, domain_service: QueueDomainService, sample_members):
        """Ошибка при одинаковых позициях."""
        with pytest.raises(InvalidPositionError):
            domain_service.replace_by_positions(sample_members, 1, 1)

    def test_replace_invalid_pos1(self, domain_service: QueueDomainService, sample_members):
        """Ошибка при невалидной первой позиции."""
        with pytest.raises(InvalidPositionError):
            domain_service.replace_by_positions(sample_members, -1, 1)

    def test_replace_invalid_pos2(self, domain_service: QueueDomainService, sample_members):
        """Ошибка при невалидной второй позиции."""
        with pytest.raises(InvalidPositionError):
            domain_service.replace_by_positions(sample_members, 1, 10)


class TestReplaceByNames:
    """Тесты для обмена по именам пользователей."""

    def test_replace_by_names_success(self, domain_service: QueueDomainService, sample_members):
        """Успешный обмен по именам."""
        pos1, pos2, name1, name2 = domain_service.replace_by_names(sample_members, "Alice", "Charlie")
        assert name1 == "Alice"
        assert name2 == "Charlie"
        assert sample_members[0]["display_name"] == "Charlie"
        assert sample_members[2]["display_name"] == "Alice"

    def test_replace_by_names_adjacent(self, domain_service: QueueDomainService, sample_members):
        """Обмен соседних пользователей по именам."""
        pos1, pos2, name1, name2 = domain_service.replace_by_names(sample_members, "Alice", "Bob")
        assert sample_members[0]["display_name"] == "Bob"
        assert sample_members[1]["display_name"] == "Alice"

    def test_replace_by_names_first_not_found(self, domain_service: QueueDomainService, sample_members):
        """Ошибка если первого пользователя нет."""
        with pytest.raises(UserNotFoundError):
            domain_service.replace_by_names(sample_members, "Unknown", "Alice")

    def test_replace_by_names_second_not_found(self, domain_service: QueueDomainService, sample_members):
        """Ошибка если второго пользователя нет."""
        with pytest.raises(UserNotFoundError):
            domain_service.replace_by_names(sample_members, "Alice", "Unknown")

    def test_replace_by_names_both_not_found(self, domain_service: QueueDomainService, sample_members):
        """Ошибка если обоих пользователей нет."""
        with pytest.raises(UserNotFoundError):
            domain_service.replace_by_names(sample_members, "Unknown1", "Unknown2")

    def test_replace_by_names_multiword_names(self, domain_service: QueueDomainService):
        """Обмен с многословными именами."""
        members = [
            {"user_id": 1, "display_name": "John Doe"},
            {"user_id": 2, "display_name": "Jane Smith"},
            {"user_id": 3, "display_name": "Bob Johnson"},
        ]
        domain_service.replace_by_names(members, "John Doe", "Bob Johnson")
        assert members[0]["display_name"] == "Bob Johnson"
        assert members[2]["display_name"] == "John Doe"


class TestComplexScenarios:
    """Тесты для сложных сценариев работы с очередью."""

    def test_remove_and_insert_sequence(self, domain_service: QueueDomainService, sample_members):
        """Последовательность удаления и вставки."""

        # Удаляем Bob
        removed_name, position = domain_service.remove_by_name(sample_members, "Bob")
        assert removed_name == "Bob"
        assert position == 2
        assert len(sample_members) == 2

        # Вставляем его в начало
        user_name, desired_pos, old_position = domain_service.insert_at_position(sample_members, "Bob", 0)
        assert desired_pos == 1
        assert sample_members[0]["display_name"] == "Bob"

    def test_multiple_replacements(self, domain_service: QueueDomainService):
        """Несколько замен подряд."""
        members = [
            {"user_id": 1, "display_name": "Alice"},
            {"user_id": 2, "display_name": "Bob"},
            {"user_id": 3, "display_name": "Charlie"},
            {"user_id": 4, "display_name": "Diana"},
        ]

        # Заменяем Alice и Bob
        pos1, pos2, name1, name2 = domain_service.replace_by_positions(members, 1, 2)
        assert members[0]["display_name"] == "Bob"
        assert members[1]["display_name"] == "Alice"

        # Заменяем Charlie и Diana
        pos1, pos2, name1, name2 = domain_service.replace_by_positions(members, 2, 3)
        assert members[1]["display_name"] == "Charlie"
        assert members[2]["display_name"] == "Alice"

    def test_insert_with_duplicate_then_remove(self, domain_service: QueueDomainService):
        """Вставка дубликата и затем удаление оригинала."""
        members = [
            {"user_id": 1, "display_name": "Alice"},
            {"user_id": 2, "display_name": "Bob"},
        ]

        # Вставляем Alice в начало (она переместится)
        user_name, desired_pos, old_position = domain_service.insert_at_position(members, "Alice", 0)
        assert old_position == 1  # была на позиции 1
        assert desired_pos == 1  # теперь на позиции 1
        assert len(members) == 2

        # Теперь удаляем Alice
        removed_name, position = domain_service.remove_by_name(members, "Alice")
        assert removed_name == "Alice"
        assert len(members) == 1
        assert members[0]["display_name"] == "Bob"
