"""
Интеграционные тесты для QueueFacadeService с моками репозитория.
"""

from unittest.mock import AsyncMock

import pytest
from telegram import User

from app.queues.models import ActionContext
from app.queues.service import QueueFacadeService
from app.services.logger import QueueLogger


@pytest.fixture
def mock_repo():
    """Мок репозитория."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_logger():
    """Мок логгера."""
    logger = AsyncMock(spec=QueueLogger)
    return logger


@pytest.fixture
def facade_service(mock_repo, mock_logger):
    """Фикстура для создания фасада сервиса с моками."""
    service = QueueFacadeService(mock_repo, logger=mock_logger)
    return service


@pytest.fixture
def action_context():
    """Пример контекста действия."""
    return ActionContext(
        chat_id=123,
        chat_title="Test Chat",
        queue_id="queue_1",
        queue_name="Test Queue",
        actor="admin",
    )


@pytest.fixture
def test_user():
    """Пример пользователя Telegram."""
    return User(
        id=1,
        is_bot=False,
        first_name="John",
        last_name="Doe",
    )


@pytest.mark.asyncio
class TestQueueFacadeServiceCreateQueue:
    """Тесты создания очереди."""

    async def test_create_queue_success(self, facade_service, mock_repo, action_context):
        """Успешное создание очереди."""
        mock_repo.create_queue = AsyncMock(return_value="queue_123")
        facade_service.auto_cleanup_service.schedule_expiration = AsyncMock()

        queue_id = await facade_service.create_queue(context=None, ctx=action_context, expires_in=3600)

        assert queue_id == "queue_123"
        mock_repo.create_queue.assert_called_once()

    async def test_create_queue_updates_context(self, facade_service, mock_repo, action_context):
        """ID очереди должен быть добавлен в контекст."""
        mock_repo.create_queue = AsyncMock(return_value="new_queue_id")
        facade_service.auto_cleanup_service.schedule_expiration = AsyncMock()

        await facade_service.create_queue(context=None, ctx=action_context, expires_in=3600)

        assert action_context.queue_id == "new_queue_id"


@pytest.mark.asyncio
class TestQueueFacadeServiceJoinQueue:
    """Тесты присоединения к очереди."""

    async def test_join_to_queue_success(self, facade_service, mock_repo, action_context, test_user):
        """Успешное добавление в очередь."""
        mock_repo.add_to_queue = AsyncMock(return_value=1)
        facade_service.user_service.get_user_display_name = AsyncMock(return_value="John Doe")

        position = await facade_service.join_to_queue(action_context, test_user)

        assert position == 1
        mock_repo.add_to_queue.assert_called_once()

    async def test_join_to_queue_multiple_users(self, facade_service, mock_repo, action_context):
        """Добавление нескольких пользователей возвращает разные позиции."""
        mock_repo.add_to_queue = AsyncMock(side_effect=[1, 2, 3])
        facade_service.user_service.get_user_display_name = AsyncMock(return_value="User")

        user1 = User(id=1, is_bot=False, first_name="User1")
        user2 = User(id=2, is_bot=False, first_name="User2")
        user3 = User(id=3, is_bot=False, first_name="User3")

        pos1 = await facade_service.join_to_queue(action_context, user1)
        pos2 = await facade_service.join_to_queue(action_context, user2)
        pos3 = await facade_service.join_to_queue(action_context, user3)

        assert pos1 == 1
        assert pos2 == 2
        assert pos3 == 3
        assert mock_repo.add_to_queue.call_count == 3


@pytest.mark.asyncio
class TestQueueFacadeServiceLeaveQueue:
    """Тесты удаления из очереди."""

    async def test_leave_from_queue_success(self, facade_service, mock_repo, action_context, test_user):
        """Успешное удаление из очереди."""
        mock_repo.remove_from_queue = AsyncMock(return_value=1)
        facade_service.user_service.get_user_display_name = AsyncMock(return_value="John Doe")

        position = await facade_service.leave_from_queue(action_context, test_user)

        assert position == 1
        mock_repo.remove_from_queue.assert_called_once()

    async def test_leave_from_queue_user_not_in_queue(self, facade_service, mock_repo, action_context, test_user):
        """Удаление несуществующего пользователя."""
        mock_repo.remove_from_queue = AsyncMock(return_value=0)

        position = await facade_service.leave_from_queue(action_context, test_user)

        assert position == 0


@pytest.mark.asyncio
class TestQueueFacadeServiceDeleteQueue:
    """Тесты удаления очереди."""

    async def test_delete_queue_success(self, facade_service, mock_repo, action_context):
        """Успешное удаление очереди."""
        mock_repo.delete_queue = AsyncMock()
        facade_service.auto_cleanup_service.cancel_expiration = AsyncMock()

        await facade_service.delete_queue(context=None, ctx=action_context)

        mock_repo.delete_queue.assert_called_once_with(123, "queue_1")

    async def test_delete_queue_cancels_expiration(self, facade_service, mock_repo, action_context):
        """Отмена истечения срока при удалении."""
        mock_repo.delete_queue = AsyncMock()
        facade_service.auto_cleanup_service.cancel_expiration = AsyncMock()

        await facade_service.delete_queue(context=None, ctx=action_context)

        facade_service.auto_cleanup_service.cancel_expiration.assert_called_once()


@pytest.mark.asyncio
class TestQueueFacadeServiceRemoveFromQueue:
    """Тесты удаления из очереди."""

    async def test_remove_from_queue_by_position(self, facade_service: QueueFacadeService, mock_repo, action_context):
        """Удаление по позиции."""
        mock_repo.get_queue_by_name = AsyncMock(
            return_value={
                "id": "queue_1",
                "members": [
                    {"user_id": 1, "display_name": "Alice"},
                    {"user_id": 2, "display_name": "Bob"},
                ],
            }
        )
        mock_repo.update_queue_members = AsyncMock()

        removed_name, position = await facade_service.remove_from_queue(action_context, pos=2)

        assert removed_name == "Bob"
        assert position == 2
        mock_repo.update_queue_members.assert_called_once()

    async def test_remove_from_queue_by_name(self, facade_service: QueueFacadeService, mock_repo, action_context):
        """Удаление по имени."""
        mock_repo.get_queue_by_name = AsyncMock(
            return_value={
                "id": "queue_1",
                "members": [
                    {"user_id": 1, "display_name": "Alice"},
                    {"user_id": 2, "display_name": "Bob"},
                ],
            }
        )
        mock_repo.update_queue_members = AsyncMock()

        removed_name, position = await facade_service.remove_from_queue(action_context, user_name="Bob")

        assert removed_name == "Bob"
        assert position == 2
        mock_repo.update_queue_members.assert_called_once()


@pytest.mark.asyncio
class TestQueueFacadeServiceInsertIntoQueue:
    """Тесты вставки в очередь."""

    async def test_insert_into_queue_at_position(self, facade_service: QueueFacadeService, mock_repo, action_context):
        """Вставка в конкретную позицию."""
        mock_repo.get_queue_by_name = AsyncMock(
            return_value={
                "id": "queue_1",
                "members": [
                    {"user_id": 1, "display_name": "Alice"},
                ],
            }
        )
        mock_repo.update_queue_members = AsyncMock()

        user_name, desired_pos, old_position = await facade_service.insert_into_queue(action_context, "Bob", 0)

        assert user_name == "Bob"
        mock_repo.update_queue_members.assert_called_once()

    async def test_insert_into_queue_at_end(self, facade_service: QueueFacadeService, mock_repo, action_context):
        """Вставка в конец очереди (без позиции)."""
        mock_repo.get_queue_by_name = AsyncMock(
            return_value={
                "id": "queue_1",
                "members": [
                    {"user_id": 1, "display_name": "Alice"},
                ],
            }
        )
        mock_repo.update_queue_members = AsyncMock()

        user_name, desired_pos, old_position = await facade_service.insert_into_queue(action_context, "Bob")

        assert user_name == "Bob"
        mock_repo.update_queue_members.assert_called_once()


@pytest.mark.asyncio
class TestQueueFacadeServiceReplaceUsers:
    """Тесты обмена в очереди."""

    async def test_replace_users_by_name(self, facade_service: QueueFacadeService, mock_repo, action_context):
        """Обмен двух пользователей по именам."""
        mock_repo.get_queue_by_name = AsyncMock(
            return_value={
                "id": "queue_1",
                "members": [
                    {"user_id": 1, "display_name": "Alice"},
                    {"user_id": 2, "display_name": "Bob"},
                ],
            }
        )
        mock_repo.update_queue_members = AsyncMock()

        pos1, pos2, name1, name2 = await facade_service.replace_users_queue(action_context, name1="Alice", name2="Bob")

        assert name1 == "Alice"
        assert name2 == "Bob"
        mock_repo.update_queue_members.assert_called_once()

    async def test_replace_users_by_position(self, facade_service: QueueFacadeService, mock_repo, action_context):
        """Обмен по позициям."""
        mock_repo.get_queue_by_name = AsyncMock(
            return_value={
                "id": "queue_1",
                "members": [
                    {"user_id": 1, "display_name": "Alice"},
                    {"user_id": 2, "display_name": "Bob"},
                ],
            }
        )
        mock_repo.update_queue_members = AsyncMock()

        pos1, pos2, name1, name2 = await facade_service.replace_users_queue(action_context, 1, 2)

        assert name1 == "Alice"
        assert name2 == "Bob"
        mock_repo.update_queue_members.assert_called_once()


@pytest.mark.asyncio
class TestQueueFacadeServiceUtilityMethods:
    """Тесты вспомогательных методов."""

    async def test_generate_queue_name(self, facade_service: QueueFacadeService, mock_repo):
        """Генерация имени очереди."""
        mock_repo.get_all_queues = AsyncMock(
            return_value={
                "q1": {"name": "Очередь 1", "members": []},
            }
        )

        result = await facade_service.generate_queue_name(123)
        assert "Очередь" in result

    async def test_get_count_queues(self, facade_service: QueueFacadeService, mock_repo):
        """Получение количества очередей."""
        mock_repo.get_all_queues = AsyncMock(
            return_value={
                "q1": {"name": "Queue 1"},
                "q2": {"name": "Queue 2"},
            }
        )

        count = await facade_service.get_count_queues(123)
        assert count == 2

    async def test_get_count_queues_empty(self, facade_service: QueueFacadeService, mock_repo):
        """Получение количества когда нет очередей."""
        mock_repo.get_all_queues = AsyncMock(return_value={})

        count = await facade_service.get_count_queues(123)
        assert count == 0

    async def test_set_queue_description(self, facade_service: QueueFacadeService, mock_repo, action_context):
        """Установка описания очереди."""
        mock_repo.set_queue_description = AsyncMock()

        await facade_service.set_queue_description(action_context, "New description")

        mock_repo.set_queue_description.assert_called_once_with(123, "queue_1", "New description")

    async def test_rename_queue(self, facade_service: QueueFacadeService, mock_repo, action_context):
        """Переименование очереди."""
        mock_repo.rename_queue = AsyncMock()

        await facade_service.rename_queue(action_context, "New Name")

        mock_repo.rename_queue.assert_called_once_with(123, "Test Queue", "New Name")


@pytest.mark.asyncio
class TestQueueFacadeServiceUserDisplayName:
    """Тесты работы с отображаемыми именами."""

    async def test_get_user_display_name_success(self, facade_service: QueueFacadeService, test_user):
        """Получение отображаемого имени."""
        facade_service.user_service.get_user_display_name = AsyncMock(return_value="John Doe")

        result = await facade_service.get_user_display_name(test_user, 123)

        assert result == "John Doe"

    async def test_set_user_display_name(self, facade_service: QueueFacadeService, action_context, test_user):
        """Установка отображаемого имени."""
        facade_service.user_service.set_user_display_name = AsyncMock()

        await facade_service.set_user_display_name(action_context, test_user, "John Custom")

        facade_service.user_service.set_user_display_name.assert_called_once()

    async def test_clear_user_display_name(self, facade_service: QueueFacadeService, action_context, test_user):
        """Очистка отображаемого имени."""
        facade_service.user_service.clear_user_display_name = AsyncMock(return_value="Default Name")

        result = await facade_service.clear_user_display_name(action_context, test_user)

        assert result == "Default Name"
