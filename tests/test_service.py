"""
Тесты для QueueFacadeService — верхнеуровневого сервиса.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.queues.errors import QueueError, QueueNotFoundError
from app.queues.models import ActionContext
from app.queues.service import QueueFacadeService


@pytest.fixture
def mock_repo():
    """Мок-объект репозитория."""
    repo = AsyncMock()
    repo.create_queue = AsyncMock()
    repo.delete_queue = AsyncMock()
    repo.add_to_queue = AsyncMock()
    repo.remove_from_queue = AsyncMock()
    repo.get_queue = AsyncMock()
    repo.update_queue = AsyncMock()
    repo.get_all_queues = AsyncMock()
    repo.rename_queue = AsyncMock()
    return repo


@pytest.fixture
def mock_keyboard_factory():
    """Мок-объект фабрики клавиатур."""
    return MagicMock(return_value=None)


@pytest.fixture
def mock_logger():
    """Мок-логгер."""
    logger = MagicMock()
    logger.log = MagicMock()
    logger.joined = MagicMock()
    logger.leaved = MagicMock()
    logger.removed = MagicMock()
    logger.inserted = MagicMock()
    logger.replaced = MagicMock()
    return logger


@pytest.fixture
def service(mock_repo, mock_keyboard_factory, mock_logger):
    """Готовый сервис с моками."""
    return QueueFacadeService(mock_repo, mock_keyboard_factory, mock_logger)


@pytest.fixture
def context():
    """Контекст действия."""
    return ActionContext(chat_id=123, chat_title="Test Chat", queue_name="Queue 1", actor="Alice")


class TestCreateQueue:
    """Тесты создания очереди."""

    @pytest.mark.asyncio
    async def test_create_queue_success(self, service, mock_repo, mock_logger, context):
        """Успешное создание очереди."""
        await service.create_queue(context)
        mock_repo.create_queue.assert_called_once_with(123, "Test Chat", "Queue 1")
        mock_logger.log.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_queue_error(self, service, mock_repo, mock_logger, context):
        """Ошибка при создании очереди."""
        mock_repo.create_queue.side_effect = QueueError("Queue already exists")
        await service.create_queue(context)
        mock_logger.log.assert_called()
        assert "QueueError" in str(mock_logger.log.call_args)


class TestDeleteQueue:
    """Тесты удаления очереди."""

    @pytest.mark.asyncio
    async def test_delete_queue_success(self, service, mock_repo, mock_logger, context):
        """Успешное удаление очереди."""
        await service.delete_queue(context)
        mock_repo.delete_queue.assert_called_once_with(123, "Queue 1")
        mock_logger.log.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_queue_not_found(self, service, mock_repo, mock_logger, context):
        """Удаление несуществующей очереди."""
        mock_repo.delete_queue.side_effect = QueueNotFoundError("Queue not found")
        await service.delete_queue(context)
        mock_logger.log.assert_called()


class TestJoinToQueue:
    """Тесты присоединения к очереди."""

    @pytest.mark.asyncio
    async def test_join_queue_success(self, service, mock_repo, mock_logger, context):
        """Успешное присоединение."""
        mock_repo.add_to_queue.return_value = 1
        position = await service.join_to_queue(context, "Bob")
        assert position == 1
        mock_repo.add_to_queue.assert_called_once_with(123, "Queue 1", "Bob")
        mock_logger.joined.assert_called_once()

    @pytest.mark.asyncio
    async def test_join_queue_error(self, service, mock_repo, mock_logger, context):
        """Ошибка при присоединении."""
        mock_repo.add_to_queue.side_effect = QueueError("Already in queue")
        position = await service.join_to_queue(context, "Bob")
        assert position is None
        mock_logger.log.assert_called()


class TestLeaveFromQueue:
    """Тесты выхода из очереди."""

    @pytest.mark.asyncio
    async def test_leave_queue_success(self, service, mock_repo, mock_logger, context):
        """Успешный выход."""
        mock_repo.remove_from_queue.return_value = 1
        position = await service.leave_from_queue(context, "Bob")
        assert position == 1
        mock_repo.remove_from_queue.assert_called_once_with(123, "Queue 1", "Bob")
        mock_logger.leaved.assert_called_once()

    @pytest.mark.asyncio
    async def test_leave_queue_error(self, service, mock_repo, mock_logger, context):
        """Ошибка при выходе."""
        mock_repo.remove_from_queue.side_effect = QueueError("Not in queue")
        position = await service.leave_from_queue(context, "Bob")
        assert position is None


class TestRemoveFromQueue:
    """Тесты удаления из очереди."""

    @pytest.mark.asyncio
    async def test_remove_by_position(self, service, mock_repo, mock_logger, context):
        """Удаление по позиции."""
        queue = ["Alice", "Bob", "Charlie"]
        mock_repo.get_queue.return_value = queue
        result = await service.remove_from_queue(context, ["2"])
        assert result.removed_name == "Bob"
        assert result.position == 2
        mock_repo.update_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_by_name(self, service, mock_repo, mock_logger, context):
        """Удаление по имени."""
        queue = ["Alice", "Bob Johnson", "Charlie"]
        mock_repo.get_queue.return_value = queue
        result = await service.remove_from_queue(context, ["Bob", "Johnson"])
        assert result.removed_name == "Bob Johnson"
        mock_repo.update_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_queue_not_found(self, service, mock_repo, mock_logger, context):
        """Очередь не найдена."""
        mock_repo.get_queue.return_value = None
        result = await service.remove_from_queue(context, ["1"])
        assert result.removed_name is None

    @pytest.mark.asyncio
    async def test_remove_invalid_position(self, service, mock_repo, mock_logger, context):
        """Неверная позиция."""
        queue = ["Alice", "Bob"]
        mock_repo.get_queue.return_value = queue
        result = await service.remove_from_queue(context, ["10"])
        assert result.removed_name is None


class TestInsertIntoQueue:
    """Тесты вставки в очередь."""

    @pytest.mark.asyncio
    async def test_insert_at_position(self, service, mock_repo, context):
        """Вставка в конкретную позицию."""
        queue = ["Alice", "Charlie"]
        mock_repo.get_queue.return_value = queue
        result = await service.insert_into_queue(context, ["Bob", "2"])
        assert result.user_name == "Bob"
        assert result.position == 2
        mock_repo.update_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_at_end(self, service, mock_repo, context):
        """Вставка в конец."""
        queue = ["Alice", "Bob"]
        mock_repo.get_queue.return_value = queue
        result = await service.insert_into_queue(context, ["Charlie"])
        assert result.user_name == "Charlie"
        assert result.position == 3

    @pytest.mark.asyncio
    async def test_insert_existing_user_moves(self, service, mock_repo, context):
        """Существующий пользователь перемещается."""
        queue = ["Alice", "Bob", "Charlie"]
        mock_repo.get_queue.return_value = queue
        result = await service.insert_into_queue(context, ["Bob", "1"])
        assert result.user_name == "Bob"
        assert result.old_position == 2


class TestReplaceUsersQueue:
    """Тесты замены пользователей."""

    @pytest.mark.asyncio
    async def test_replace_by_positions(self, service, mock_repo, mock_logger, context):
        """Замена по позициям."""
        queue = ["Alice", "Bob", "Charlie"]
        mock_repo.get_queue.return_value = queue
        result = await service.replace_users_queue(context, ["1", "3"])
        assert result.user1 == "Alice"
        assert result.user2 == "Charlie"
        mock_repo.update_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_replace_by_names(self, service, mock_repo, mock_logger, context):
        """Замена по именам."""
        queue = ["Alice", "Bob", "Charlie"]
        mock_repo.get_queue.return_value = queue
        result = await service.replace_users_queue(context, ["Alice", "Charlie"])
        assert result.user1 == "Alice"
        assert result.user2 == "Charlie"

    @pytest.mark.asyncio
    async def test_replace_queue_not_found(self, service, mock_repo, context):
        """Очередь не найдена."""
        mock_repo.get_queue.return_value = None
        result = await service.replace_users_queue(context, ["1", "2"])
        assert result.updated_queue is None


class TestGetQueueIndex:
    """Тесты получения индекса очереди."""

    @pytest.mark.asyncio
    async def test_get_queue_index(self, service, mock_repo):
        """Получить индекс очереди."""
        mock_repo.get_all_queues.return_value = {
            "Queue 1": {"queue": []},
            "Queue 2": {"queue": []},
            "Queue 3": {"queue": []},
        }
        index = await service.get_queue_index(123, "Queue 2")
        assert index == 1

    @pytest.mark.asyncio
    async def test_get_queue_index_not_found(self, service, mock_repo):
        """Очередь не найдена."""
        mock_repo.get_all_queues.return_value = {"Queue 1": {"queue": []}}
        with pytest.raises(QueueNotFoundError):
            await service.get_queue_index(123, "Unknown")


class TestRenameQueue:
    """Тесты переименования очереди."""

    @pytest.mark.asyncio
    async def test_rename_queue_success(self, service, mock_repo, mock_logger, context):
        """Успешное переименование."""
        await service.rename_queue(context, "New Queue")
        mock_repo.rename_queue.assert_called_once_with(123, "Queue 1", "New Queue")

    @pytest.mark.asyncio
    async def test_rename_queue_error(self, service, mock_repo, mock_logger, context):
        """Ошибка при переименовании."""
        mock_repo.rename_queue.side_effect = QueueError("Queue not found")
        await service.rename_queue(context, "New Queue")
        mock_logger.log.assert_called()


class TestGenerateQueueName:
    """Тесты генерации имени очереди."""

    @pytest.mark.asyncio
    async def test_generate_queue_name(self, service, mock_repo):
        """Генерация имени очереди."""
        mock_repo.get_all_queues.return_value = {"Очередь 1": {"queue": ["Alice"]}, "Очередь 2": {"queue": []}}
        name = await service.generate_queue_name(123)
        assert name == "Очередь 2"


class TestGetCountQueues:
    """Тесты получения количества очередей."""

    @pytest.mark.asyncio
    async def test_get_count_queues(self, service, mock_repo):
        """Получить количество очередей."""
        mock_repo.get_all_queues.return_value = {
            "Queue 1": {"queue": []},
            "Queue 2": {"queue": []},
            "Queue 3": {"queue": []},
        }
        count = await service.get_count_queues(123)
        assert count == 3

    @pytest.mark.asyncio
    async def test_get_count_queues_empty(self, service, mock_repo):
        """Количество очередей при пустом словаре."""
        mock_repo.get_all_queues.return_value = {}
        count = await service.get_count_queues(123)
        assert count == 0
