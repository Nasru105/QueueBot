import asyncio
from unittest.mock import MagicMock

import pytest

from app.queues.services.swap_service.swap_service import SwapNotFound, SwapPermissionError, SwapService


@pytest.fixture
def swap_service():
    """Создает новый экземпляр SwapService для каждого теста."""
    return SwapService()


@pytest.mark.asyncio
class TestSwapService:
    async def test_create_swap(self, swap_service):
        """Тест создания запроса на обмен."""
        chat_id = 123
        queue_id = "q1"
        requester_id = 1
        target_id = 2
        requester_name = "Alice"
        target_name = "Bob"
        queue_name = "Test Queue"

        swap_id = await swap_service.create_swap(
            chat_id=chat_id,
            queue_id=queue_id,
            requester_id=requester_id,
            target_id=target_id,
            requester_name=requester_name,
            target_name=target_name,
            queue_name=queue_name,
            ttl=120,
        )

        # Проверяем, что ID создан
        assert swap_id is not None
        assert isinstance(swap_id, str)
        assert len(swap_id) == 32  # uuid4().hex имеет длину 32

        # Проверяем, что данные сохранены
        swap = await swap_service.get_swap(swap_id)
        assert swap is not None
        assert swap["chat_id"] == chat_id
        assert swap["queue_id"] == queue_id
        assert swap["requester_id"] == requester_id
        assert swap["target_id"] == target_id
        assert swap["requester_name"] == requester_name
        assert swap["target_name"] == target_name
        assert swap["queue_name"] == queue_name

    async def test_create_swap_generates_unique_ids(self, swap_service):
        """Тест, что каждый swap имеет уникальный ID."""
        swap_id1 = await swap_service.create_swap(123, "q1", 1, 2)
        swap_id2 = await swap_service.create_swap(123, "q1", 3, 4)

        assert swap_id1 != swap_id2

    async def test_get_swap_existing(self, swap_service):
        """Тест получения существующего swap."""
        swap_id = await swap_service.create_swap(123, "q1", 1, 2, "Alice", "Bob", "Queue")

        swap = await swap_service.get_swap(swap_id)

        assert swap is not None
        assert swap["requester_id"] == 1
        assert swap["target_id"] == 2

    async def test_get_swap_nonexistent(self, swap_service):
        """Тест получения несуществующего swap возвращает None."""
        swap = await swap_service.get_swap("nonexistent_id")

        assert swap is None

    async def test_delete_swap(self, swap_service):
        """Тест удаления swap."""
        swap_id = await swap_service.create_swap(123, "q1", 1, 2)

        # Проверяем, что существует
        swap = await swap_service.get_swap(swap_id)
        assert swap is not None

        # Удаляем
        await swap_service.delete_swap(swap_id)

        # Проверяем, что удален
        swap = await swap_service.get_swap(swap_id)
        assert swap is None

    async def test_delete_nonexistent_swap(self, swap_service):
        """Тест удаления несуществующего swap не вызывает ошибку."""
        # Не должно быть исключения
        await swap_service.delete_swap("nonexistent_id")

    async def test_add_task_to_swap(self, swap_service):
        """Тест добавления задачи к swap."""
        swap_id = await swap_service.create_swap(123, "q1", 1, 2)
        mock_task = MagicMock()

        await swap_service.add_task_to_swap(swap_id, mock_task)

        swap = await swap_service.get_swap(swap_id)
        assert swap["task"] == mock_task

    async def test_add_task_overwrite(self, swap_service):
        """Тест, что добавление задачи не перезаписывает существующую."""
        swap_id = await swap_service.create_swap(123, "q1", 1, 2)
        task1 = MagicMock()
        task2 = MagicMock()

        await swap_service.add_task_to_swap(swap_id, task1)
        await swap_service.add_task_to_swap(swap_id, task2)

        swap = await swap_service.get_swap(swap_id)
        # setdefault не перезаписывает, поэтому task1 остается
        assert swap["task"] == task1

    async def test_respond_swap_success(self, swap_service):
        """Тест успешного ответа на запрос обмена."""
        swap_id = await swap_service.create_swap(
            chat_id=123,
            queue_id="q1",
            requester_id=1,
            target_id=2,
            requester_name="Alice",
            target_name="Bob",
        )

        result = await swap_service.respond_swap(swap_id, by_user_id=2)

        # Проверяем, что вернулись данные swap
        assert result["requester_id"] == 1
        assert result["target_id"] == 2

        # Проверяем, что swap был удален
        swap = await swap_service.get_swap(swap_id)
        assert swap is None

    async def test_respond_swap_not_found(self, swap_service):
        """Тест ответа на несуществующий swap вызывает исключение."""
        with pytest.raises(SwapNotFound):
            await swap_service.respond_swap("nonexistent_id", by_user_id=2)

    async def test_respond_swap_permission_denied(self, swap_service):
        """Тест ответа от неправильного пользователя вызывает исключение."""
        swap_id = await swap_service.create_swap(123, "q1", 1, 2)

        # Пытаемся ответить от пользователя 99, а не 2 (target_id)
        with pytest.raises(SwapPermissionError):
            await swap_service.respond_swap(swap_id, by_user_id=99)

    async def test_respond_swap_permission_string_vs_int(self, swap_service):
        """Тест, что сравнение user_id работает при разных типах (str vs int)."""
        swap_id = await swap_service.create_swap(123, "q1", 1, 2)

        # Передаем target_id как строку
        result = await swap_service.respond_swap(swap_id, by_user_id="2")

        assert result["target_id"] == 2

    async def test_respond_swap_cancels_task(self, swap_service):
        """Тест, что ответ на swap отменяет привязанную задачу."""
        swap_id = await swap_service.create_swap(123, "q1", 1, 2)
        mock_task = MagicMock()
        mock_task.cancel = MagicMock()

        await swap_service.add_task_to_swap(swap_id, mock_task)
        await swap_service.respond_swap(swap_id, by_user_id=2)

        mock_task.cancel.assert_called_once()

    async def test_respond_swap_no_task(self, swap_service):
        """Тест, что ответ работает если не было задачи."""
        swap_id = await swap_service.create_swap(123, "q1", 1, 2)

        # Не добавляем задачу
        result = await swap_service.respond_swap(swap_id, by_user_id=2)

        assert result is not None

    async def test_expire_swap(self, swap_service):
        """Тест автоматического удаления swap после TTL."""
        swap_id = await swap_service.create_swap(123, "q1", 1, 2, ttl=1)

        # Проверяем, что существует
        swap = await swap_service.get_swap(swap_id)
        assert swap is not None

        # Ждем истечения TTL
        await asyncio.sleep(1.1)

        # Проверяем, что удален
        swap = await swap_service.get_swap(swap_id)
        assert swap is None

    async def test_multiple_swaps(self, swap_service):
        """Тест управления несколькими одновременными swaps."""
        swap_id1 = await swap_service.create_swap(123, "q1", 1, 2)
        swap_id2 = await swap_service.create_swap(123, "q1", 3, 4)
        swap_id3 = await swap_service.create_swap(456, "q2", 5, 6)

        # Все должны существовать
        assert await swap_service.get_swap(swap_id1) is not None
        assert await swap_service.get_swap(swap_id2) is not None
        assert await swap_service.get_swap(swap_id3) is not None

        # Удаляем один
        await swap_service.delete_swap(swap_id2)

        # Остальные все еще существуют
        assert await swap_service.get_swap(swap_id1) is not None
        assert await swap_service.get_swap(swap_id2) is None
        assert await swap_service.get_swap(swap_id3) is not None

    async def test_swap_with_optional_params(self, swap_service):
        """Тест создания swap с минимальными параметрами."""
        swap_id = await swap_service.create_swap(
            chat_id=123,
            queue_id="q1",
            requester_id=1,
            target_id=2,
        )

        swap = await swap_service.get_swap(swap_id)

        # Опциональные параметры должны быть None
        assert swap["requester_name"] is None
        assert swap["target_name"] is None
        assert swap["queue_name"] is None

    async def test_swap_storage_isolation(self, swap_service):
        """Тест, что каждый SwapService имеет собственное хранилище."""
        service1 = SwapService()
        service2 = SwapService()

        swap_id1 = await service1.create_swap(123, "q1", 1, 2)
        swap_id2 = await service2.create_swap(123, "q1", 3, 4)

        # Каждый сервис видит только свои swaps
        assert await service1.get_swap(swap_id1) is not None
        assert await service1.get_swap(swap_id2) is None

        assert await service2.get_swap(swap_id2) is not None
        assert await service2.get_swap(swap_id1) is None
