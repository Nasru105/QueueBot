"""
Тесты для моделей данных.
"""

from app.queues.models import ActionContext, InsertResult, QueueEntity, RemoveResult, ReplaceResult


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


class TestQueueEntity:
    """Тесты для QueueEntity."""

    def test_queue_entity_creation(self):
        """Создание сущности очереди."""
        items = [
            {"user_id": 1, "display_name": "Alice"},
            {"user_id": 2, "display_name": "Bob"},
        ]
        queue = QueueEntity(
            chat_id=123,
            name="Test Queue",
            items=items,
        )
        assert queue.chat_id == 123
        assert queue.name == "Test Queue"
        assert queue.items == items
        assert queue.last_queue_message_id is None

    def test_queue_entity_with_message_id(self):
        """Создание очереди с ID последнего сообщения."""
        queue = QueueEntity(
            chat_id=123,
            name="Test Queue",
            items=[],
            last_queue_message_id=789,
        )
        assert queue.last_queue_message_id == 789

    def test_queue_entity_with_empty_items(self):
        """Создание пустой очереди."""
        queue = QueueEntity(
            chat_id=123,
            name="Empty Queue",
            items=[],
        )
        assert len(queue.items) == 0


class TestRemoveResult:
    """Тесты для RemoveResult."""

    def test_remove_result_successful(self):
        """Результат успешного удаления."""
        queue = [
            {"user_id": 2, "display_name": "Bob"},
        ]
        result = RemoveResult(
            removed_name="Alice",
            position=1,
            updated_queue=queue,
        )
        assert result.removed_name == "Alice"
        assert result.position == 1
        assert len(result.updated_queue) == 1

    def test_remove_result_not_found(self):
        """Результат когда пользователь не найден."""
        result = RemoveResult(
            removed_name=None,
            position=None,
            updated_queue=None,
        )
        assert result.removed_name is None
        assert result.position is None
        assert result.updated_queue is None

    def test_remove_result_is_named_tuple(self):
        """RemoveResult должна быть NamedTuple."""
        result = RemoveResult("Alice", 1, [])
        # Проверяем что можно обращаться как к кортежу
        assert result[0] == "Alice"
        assert result[1] == 1


class TestInsertResult:
    """Тесты для InsertResult."""

    def test_insert_result_successful(self):
        """Результат успешной вставки."""
        queue = [
            {"user_id": None, "display_name": "Alice"},
            {"user_id": 1, "display_name": "Bob"},
        ]
        result = InsertResult(
            user_name="Alice",
            position=1,
            updated_queue=queue,
            old_position=None,
        )
        assert result.user_name == "Alice"
        assert result.position == 1
        assert result.old_position is None
        assert len(result.updated_queue) == 2

    def test_insert_result_with_old_position(self):
        """Результат вставки с перемещением (был в позиции 3, переместился на 1)."""
        queue = [
            {"user_id": None, "display_name": "Alice"},
            {"user_id": 2, "display_name": "Bob"},
        ]
        result = InsertResult(
            user_name="Alice",
            position=1,
            updated_queue=queue,
            old_position=3,
        )
        assert result.old_position == 3
        assert result.position == 1

    def test_insert_result_is_named_tuple(self):
        """InsertResult должна быть NamedTuple."""
        result = InsertResult("Alice", 1, [], None)
        assert result[0] == "Alice"
        assert result[1] == 1


class TestReplaceResult:
    """Тесты для ReplaceResult."""

    def test_replace_result_successful(self):
        """Результат успешного обмена."""
        queue = [
            {"user_id": 3, "display_name": "Charlie"},
            {"user_id": 2, "display_name": "Bob"},
            {"user_id": 1, "display_name": "Alice"},
        ]
        result = ReplaceResult(
            queue_name="Test Queue",
            updated_queue=queue,
            pos1=0,
            pos2=2,
            user1="Alice",
            user2="Charlie",
        )
        assert result.queue_name == "Test Queue"
        assert result.user1 == "Alice"
        assert result.user2 == "Charlie"
        assert result.pos1 == 0
        assert result.pos2 == 2

    def test_replace_result_is_named_tuple(self):
        """ReplaceResult должна быть NamedTuple."""
        result = ReplaceResult("Queue", [], 0, 1, "User1", "User2")
        assert result[0] == "Queue"
        assert result[4] == "User1"
