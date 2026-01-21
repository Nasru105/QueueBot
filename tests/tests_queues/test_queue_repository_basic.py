"""
Тесты для queue_repository.py - операции с MongoDB
Фокус на основные методы: create_queue, add_to_queue, remove_from_queue, update_queue_members
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.queues.errors import QueueNotFoundError, UserAlreadyExistsError, UserNotFoundError
from app.queues.models import Queue
from app.queues.queue_repository import QueueRepository


@pytest.fixture
def mock_db():
    """Создает мокированную БД"""
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    return mock_db, mock_collection


@pytest.fixture
def repository(mock_db):
    """Создает QueueRepository с мокированной БД"""
    mock_db_obj, mock_collection = mock_db
    repo = QueueRepository(mock_db_obj)
    return repo


class TestQueueRepositoryChatOperations:
    """Тесты для операций с чатами"""

    @pytest.mark.asyncio
    async def test_get_chat_new(self, repository: QueueRepository):
        """Создание нового чата при первом обращении"""
        repository.queue_collection.find_one = AsyncMock(return_value=None)
        repository.queue_collection.insert_one = AsyncMock()

        result = await repository.get_chat(123)

        assert result["chat_id"] == 123
        assert result["queues"] == {}
        assert result["last_list_message_id"] is None
        repository.queue_collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_chat_existing(self, repository: QueueRepository):
        """Получение существующего чата"""
        existing_chat = {"chat_id": 123, "queues": {}, "last_list_message_id": None}
        repository.queue_collection.find_one = AsyncMock(return_value=existing_chat)

        result = await repository.get_chat(123)

        assert result == existing_chat
        repository.queue_collection.insert_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_chat(self, repository: QueueRepository):
        """Обновление данных чата"""
        repository.queue_collection.update_one = AsyncMock()

        await repository.update_chat(123, {"chat_title": "NewTitle"})

        repository.queue_collection.update_one.assert_called_once()


class TestQueueRepositoryQueueOperations:
    """Тесты для операций с очередями"""

    @pytest.mark.asyncio
    async def test_create_queue_success(self, repository: QueueRepository):
        """Успешное создание очереди"""
        repository.queue_collection.find_one = AsyncMock(return_value={"chat_id": 123, "queues": {}})
        repository.queue_collection.update_one = AsyncMock()

        with patch("app.queues.queue_repository.uuid4") as mock_uuid:
            mock_uuid.return_value.hex = "testuuid"
            result = await repository.create_queue(123, "TestChat", "MyQueue")

            assert result == "testuuid"  # первые 8 символов
            repository.queue_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_queue_duplicate(self, repository: QueueRepository):
        """Возврат ID дублирующейся очереди"""
        existing_queue = {
            "chat_id": 123,
            "queues": {"q1": {"id": "q1", "name": "MyQueue", "members": []}},
        }
        repository.queue_collection.find_one = AsyncMock(return_value=existing_queue)

        result = await repository.create_queue(123, "TestChat", "MyQueue")

        assert result == "q1"  # должен вернуть ID существующей очереди
        repository.queue_collection.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_queue_success(self, repository: QueueRepository):
        """Успешное получение очереди"""
        queue_dict = {
            "id": "q1",
            "name": "MyQueue",
            "members": [{"user_id": 1, "display_name": "Alice"}],
            "description": None,
            "last_queue_message_id": None,
            "last_modified": None,
            "expiration": None,
        }
        repository.queue_collection.find_one = AsyncMock(return_value={"chat_id": 123, "queues": {"q1": queue_dict}})

        result = await repository.get_queue(123, "q1")

        assert isinstance(result, Queue)
        assert result.id == "q1"
        assert result.name == "MyQueue"
        assert len(result.members) == 1

    @pytest.mark.asyncio
    async def test_get_queue_not_found(self, repository: QueueRepository):
        """Ошибка при получении несуществующей очереди"""
        repository.queue_collection.find_one = AsyncMock(return_value={"chat_id": 123, "queues": {}})

        with pytest.raises(QueueNotFoundError):
            await repository.get_queue(123, "nonexistent")

    @pytest.mark.asyncio
    async def test_delete_queue(self, repository: QueueRepository):
        """Удаление очереди"""
        repository.queue_collection.find_one = AsyncMock(
            return_value={"chat_id": 123, "queues": {"q1": {"id": "q1", "name": "MyQueue"}}}
        )
        repository.queue_collection.update_one = AsyncMock()
        repository.queue_collection.delete_one = AsyncMock()

        await repository.delete_queue(123, "q1")

        # После удаления последней очереди документ должен быть удален
        repository.queue_collection.delete_one.assert_called_once()


class TestQueueRepositoryMemberOperations:
    """Тесты для операций с участниками"""

    @pytest.mark.asyncio
    async def test_add_to_queue_success(self, repository: QueueRepository):
        """Успешное добавление участника в очередь"""
        repository.queue_collection.find_one = AsyncMock(
            return_value={"chat_id": 123, "queues": {"q1": {"members": []}}}
        )
        repository.queue_collection.update_one = AsyncMock()

        result = await repository.add_to_queue(123, "q1", 1, "Alice")

        assert result == 1  # позиция в очереди
        repository.queue_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_to_queue_duplicate_user(self, repository: QueueRepository):
        """Ошибка при добавлении дублирующегося пользователя"""
        repository.queue_collection.find_one = AsyncMock(
            return_value={
                "chat_id": 123,
                "queues": {"q1": {"members": [{"user_id": 1, "display_name": "Alice"}]}},
            }
        )

        with pytest.raises(UserAlreadyExistsError):
            await repository.add_to_queue(123, "q1", 1, "Alice")

    @pytest.mark.asyncio
    async def test_remove_from_queue_success(self, repository: QueueRepository):
        """Успешное удаление участника из очереди"""
        repository.queue_collection.find_one = AsyncMock(
            return_value={
                "chat_id": 123,
                "queues": {
                    "q1": {
                        "members": [
                            {"user_id": 1, "display_name": "Alice"},
                            {"user_id": 2, "display_name": "Bob"},
                        ]
                    }
                },
            }
        )
        repository.queue_collection.update_one = AsyncMock()

        result = await repository.remove_from_queue(123, "q1", 1)

        assert result == 1  # позиция, с которой удален
        repository.queue_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_from_queue_not_found(self, repository: QueueRepository):
        """Ошибка при удалении несуществующего пользователя"""
        repository.queue_collection.find_one = AsyncMock(
            return_value={
                "chat_id": 123,
                "queues": {"q1": {"members": [{"user_id": 1, "display_name": "Alice"}]}},
            }
        )

        with pytest.raises(UserNotFoundError):
            await repository.remove_from_queue(123, "q1", 999)


class TestQueueRepositoryMessageOperations:
    """Тесты для операций с сохранением ID сообщений"""

    @pytest.mark.asyncio
    async def test_set_queue_message_id(self, repository: QueueRepository):
        """Сохранение ID сообщения очереди"""
        repository.queue_collection.find_one = AsyncMock(return_value={"chat_id": 123, "queues": {"q1": {}}})
        repository.queue_collection.update_one = AsyncMock()

        await repository.set_queue_message_id(123, "q1", 42)

        repository.queue_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_queue_message_id(self, repository: QueueRepository):
        """Получение ID сообщения очереди"""
        repository.queue_collection.find_one = AsyncMock(
            return_value={"chat_id": 123, "queues": {"q1": {"last_queue_message_id": 42}}}
        )

        result = await repository.get_queue_message_id(123, "q1")

        assert result == 42

    @pytest.mark.asyncio
    async def test_set_list_message_id(self, repository: QueueRepository):
        """Сохранение ID сообщения списка"""
        repository.queue_collection.find_one = AsyncMock(return_value={"chat_id": 123})
        repository.queue_collection.update_one = AsyncMock()

        await repository.set_list_message_id(123, 99)

        repository.queue_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_list_message_id(self, repository: QueueRepository):
        """Получение ID сообщения списка"""
        repository.queue_collection.find_one = AsyncMock(return_value={"chat_id": 123, "last_list_message_id": 99})

        result = await repository.get_list_message_id(123)

        assert result == 99


class TestQueueRepositoryQueueProperties:
    """Тесты для операций с свойствами очереди"""

    @pytest.mark.asyncio
    async def test_set_queue_description(self, repository: QueueRepository):
        """Установка описания очереди"""
        repository.queue_collection.update_one = AsyncMock()

        await repository.set_queue_description(123, "q1", "New description")

        repository.queue_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_rename_queue(self, repository: QueueRepository):
        """Переименование очереди"""
        repository.queue_collection.find_one = AsyncMock(
            return_value={
                "chat_id": 123,
                "queues": {"q1": {"id": "q1", "name": "OldName", "members": []}},
            }
        )
        repository.queue_collection.update_one = AsyncMock()

        await repository.rename_queue(123, "OldName", "NewName")

        repository.queue_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_queues(self, repository: QueueRepository):
        """Получение всех очередей чата"""
        queue_dict = {
            "id": "q1",
            "name": "Queue1",
            "members": [],
            "description": None,
            "last_queue_message_id": None,
            "last_modified": None,
            "expiration": None,
        }
        repository.queue_collection.find_one = AsyncMock(return_value={"chat_id": 123, "queues": {"q1": queue_dict}})

        result = await repository.get_all_queues(123)

        assert "q1" in result
        assert isinstance(result["q1"], Queue)


class TestQueueRepositoryExpirationOperations:
    """Тесты для операций с истечением очереди"""

    @pytest.mark.asyncio
    async def test_set_queue_expiration(self, repository: QueueRepository):
        """Установка времени истечения очереди"""
        repository.queue_collection.update_one = AsyncMock()

        expiration = datetime(2025, 12, 31, 23, 59, 59)
        await repository.set_queue_expiration(123, "q1", expiration)

        repository.queue_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_queue_expiration(self, repository: QueueRepository):
        """Очистка времени истечения очереди"""
        repository.queue_collection.update_one = AsyncMock()

        await repository.clear_queue_expiration(123, "q1")

        repository.queue_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_queue_expiration(self, repository: QueueRepository):
        """Получение времени истечения очереди"""
        expiration = datetime(2025, 12, 31, 23, 59, 59)
        repository.queue_collection.find_one = AsyncMock(
            return_value={"chat_id": 123, "queues": {"q1": {"expiration": expiration}}}
        )

        result = await repository.get_queue_expiration(123, "q1")

        assert result == expiration
