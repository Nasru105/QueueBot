"""
Тесты для моделей данных.
"""

import pytest

from app.queues.errors import UserNotFoundError
from app.queues.models import ActionContext, Member, Queue


class TestActionContext:
    """Тесты для ActionContext."""

    def test_action_context_creation_defaults(self):
        """Создание контекста с значениями по умолчанию."""
        ctx = ActionContext()
        assert ctx.chat_id == 0
        assert ctx.chat_title == ""
        assert ctx.queue_id == ""
        assert ctx.queue_name == ""
        assert ctx.actor == ""
        assert ctx.thread_id is None

    def test_action_context_creation_with_values(self):
        """Создание контекста с конкретными значениями."""
        ctx = ActionContext(
            chat_id=123,
            chat_title="Test Chat",
            queue_id="q1",
            queue_name="Queue 1",
            actor="admin",
            thread_id=456,
        )
        assert ctx.chat_id == 123
        assert ctx.chat_title == "Test Chat"
        assert ctx.queue_id == "q1"
        assert ctx.queue_name == "Queue 1"
        assert ctx.actor == "admin"
        assert ctx.thread_id == 456

    def test_action_context_is_mutable(self):
        """Контекст должен быть изменяемым."""
        ctx = ActionContext(chat_id=123)
        ctx.queue_id = "new_queue"
        assert ctx.queue_id == "new_queue"


class TestQueue:
    """Тесты для Queue."""

    def test_queue_creation(self):
        """Создание очереди."""
        members = [
            Member(user_id=1, display_name="Alice"),
            Member(user_id=2, display_name="Bob"),
        ]
        queue = Queue(
            id="q1",
            name="Test Queue",
            members=members,
        )
        assert queue.id == "q1"
        assert queue.name == "Test Queue"
        assert len(queue.members) == 2
        assert queue.last_queue_message_id is None

    def test_queue_with_message_id(self):
        """Создание очереди с ID последнего сообщения."""
        queue = Queue(
            id="q1",
            name="Test Queue",
            members=[],
            last_queue_message_id=789,
        )
        assert queue.last_queue_message_id == 789

    def test_queue_with_empty_members(self):
        """Создание пустой очереди."""
        queue = Queue(
            id="q1",
            name="Empty Queue",
            members=[],
        )
        assert len(queue.members) == 0


class TestQueueRemove:
    """Тесты для удаления из очереди."""

    def test_remove_successful(self):
        """Результат успешного удаления."""
        queue = Queue(
            id="q1",
            name="Test Queue",
            members=[
                Member(user_id=1, display_name="Alice"),
                Member(user_id=2, display_name="Bob"),
            ],
        )
        removed_name, position = queue.remove("Alice")
        assert removed_name == "Alice"
        assert position == 1
        assert len(queue.members) == 1

    def test_remove_not_found(self):
        """Ошибка при удалении несуществующего пользователя."""
        queue = Queue(id="q1", name="Test Queue", members=[Member(user_id=1, display_name="Bob")])
        with pytest.raises(UserNotFoundError):
            queue.remove("Alice")

    def test_remove_from_single_member_queue(self):
        """Удаление единственного пользователя."""
        queue = Queue(id="q1", name="Test Queue", members=[Member(user_id=1, display_name="Alice")])
        removed_name, position = queue.remove("Alice")
        assert removed_name == "Alice"
        assert position == 1
        assert len(queue.members) == 0


class TestQueueInsert:
    """Тесты для вставки в очередь."""

    def test_insert_successful(self):
        """Результат успешной вставки."""
        queue = Queue(id="q1", name="Test Queue", members=[Member(user_id=1, display_name="Bob")])
        old_position, position = queue.insert("Alice", user_id=2)
        assert position == 2
        assert old_position is None
        assert len(queue.members) == 2
        assert queue.members[-1].display_name == "Alice"

    def test_insert_with_old_position(self):
        """Результат вставки с перемещением (был в позиции 1, переместился на 2)."""
        queue = Queue(
            id="q1",
            name="Test Queue",
            members=[
                Member(user_id=1, display_name="Alice"),
                Member(user_id=2, display_name="Bob"),
            ],
        )
        old_position, position = queue.insert("Alice", desired_pos=1)
        assert old_position == 1
        assert position == 2
        assert len(queue.members) == 2

    def test_insert_at_specific_position(self):
        """Вставка в конкретную позицию."""
        queue = Queue(
            id="q1",
            name="Test Queue",
            members=[
                Member(user_id=1, display_name="Alice"),
                Member(user_id=3, display_name="Charlie"),
            ],
        )
        old_position, position = queue.insert("Bob", desired_pos=1, user_id=2)
        assert position == 2
        assert queue.members[1].display_name == "Bob"


class TestQueueSwap:
    """Тесты для обмена местами в очереди."""

    def test_swap_by_position_successful(self):
        """Результат успешного обмена."""
        queue = Queue(
            id="q1",
            name="Test Queue",
            members=[
                Member(user_id=1, display_name="Alice"),
                Member(user_id=2, display_name="Bob"),
                Member(user_id=3, display_name="Charlie"),
            ],
        )
        pos1, pos2, name1, name2 = queue.swap_by_position(0, 2)
        assert name1 == "Alice"
        assert name2 == "Charlie"
        assert pos1 == 1
        assert pos2 == 3
        assert queue.members[0].display_name == "Charlie"
        assert queue.members[2].display_name == "Alice"

    def test_swap_by_name_successful(self):
        """Успешный обмен по именам."""
        queue = Queue(
            id="q1",
            name="Test Queue",
            members=[
                Member(user_id=1, display_name="Alice"),
                Member(user_id=2, display_name="Bob"),
                Member(user_id=3, display_name="Charlie"),
            ],
        )
        pos1, pos2, name1, name2 = queue.swap_by_name("Alice", "Charlie")
        assert name1 == "Alice"
        assert name2 == "Charlie"
        assert queue.members[0].display_name == "Charlie"
        assert queue.members[2].display_name == "Alice"
