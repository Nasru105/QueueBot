from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import User

from app.queues.models import ActionContext
from app.queues.services.swap_service.swap_handler import request_swap, respond_swap

MODULE_PATH = "app.queues.services.swap_service.swap_handler"


@pytest.fixture
def mock_context():
    """Создает мок Telegram контекста."""
    context = MagicMock()
    context.bot = AsyncMock()
    return context


@pytest.fixture
def mock_user():
    """Создает мок пользователя Telegram."""
    user = MagicMock(spec=User)
    # По умолчанию ID строковый, как в некоторых старых тестах,
    # но лучше приводить к int в тестах, где важен тип.
    user.id = 123
    user.first_name = "Alice"
    return user


@pytest.fixture
def mock_ctx():
    """Создает ActionContext для тестов."""
    return ActionContext(
        chat_id=999,
        chat_title="Test Chat",
        queue_id="test_queue",
        queue_name="Test Queue",
        actor="tester",
    )


@pytest.fixture
def sample_members():
    """Создает список членов очереди."""
    return [
        {"user_id": 123, "display_name": "Alice"},
        {"user_id": 456, "display_name": "Bob"},
        {"user_id": 789, "display_name": "Charlie"},
    ]


@pytest.mark.asyncio
class TestRequestSwap:
    async def test_request_swap_success(self, mock_context, mock_user, mock_ctx, sample_members):
        """Тест успешного запроса на обмен."""
        with (
            patch(f"{MODULE_PATH}.swap_service") as mock_swap_service,
            patch(f"{MODULE_PATH}.swap_confirmation_keyboard") as mock_keyboard,
            patch(f"{MODULE_PATH}.delete_message_later") as mock_delete_later,
            patch(f"{MODULE_PATH}.QueueLogger") as mock_logger,
        ):
            mock_swap_service.create_swap = AsyncMock(return_value="swap_123")
            mock_swap_service.add_task_to_swap = AsyncMock()
            mock_keyboard.return_value = MagicMock()
            mock_delete_later.return_value = MagicMock()

            await request_swap(
                mock_context,
                mock_ctx,
                sample_members,
                mock_user,
                target_id="456",  # Bob
            )

            # Проверяем, что swap создан
            mock_swap_service.create_swap.assert_awaited_once()
            call_kwargs = mock_swap_service.create_swap.call_args[1]
            assert call_kwargs["chat_id"] == 999
            assert call_kwargs["queue_id"] == "test_queue"
            assert call_kwargs["requester_id"] == 123
            assert call_kwargs["target_id"] == 456
            assert call_kwargs["requester_name"] == "Alice"
            assert call_kwargs["target_name"] == "Bob"
            assert call_kwargs["ttl"] == 120

            # Проверяем, что сообщение было создано
            mock_delete_later.assert_awaited_once()

            # Проверяем, что задача привязана к swap
            mock_swap_service.add_task_to_swap.assert_awaited_once_with("swap_123", mock_delete_later.return_value)

            # Проверяем логирование
            mock_logger.log.assert_called_once()

    async def test_request_swap_same_user(self, mock_context, mock_user, mock_ctx, sample_members):
        """Тест запроса обмена у самого себя - должен быть пропущен."""
        with patch(f"{MODULE_PATH}.swap_service"):
            # Пытаемся запросить обмен местом с самим собой
            await request_swap(
                mock_context,
                mock_ctx,
                sample_members,
                mock_user,
                target_id="123",  # Такой же ID как у requester
            )
            # Не должно быть никаких действий

    async def test_request_swap_invalid_user_id(self, mock_context, mock_user, mock_ctx, sample_members):
        """Тест с невалидным ID пользователя."""
        with patch(f"{MODULE_PATH}.swap_service"):
            # Целевой пользователь не найден
            await request_swap(
                mock_context,
                mock_ctx,
                sample_members,
                mock_user,
                target_id="999",  # Нет такого в members
            )
            # Не должно быть никаких действий

    async def test_request_swap_invalid_requester_id(self, mock_context, mock_user, mock_ctx, sample_members):
        """Тест когда requester не найден в очереди."""
        mock_user.id = 999  # Не в списке members
        with patch(f"{MODULE_PATH}.swap_service"):
            await request_swap(
                mock_context,
                mock_ctx,
                sample_members,
                mock_user,
                target_id="456",
            )
            # Не должно быть никаких действий

    async def test_request_swap_string_ids(self, mock_context, mock_user, mock_ctx, sample_members):
        """Тест обработки ID как строк."""
        mock_user.id = "123"  # Проверяем строковый ID
        with (
            patch(f"{MODULE_PATH}.swap_service") as mock_swap_service,
            patch(f"{MODULE_PATH}.swap_confirmation_keyboard"),
            patch(f"{MODULE_PATH}.delete_message_later"),
            patch(f"{MODULE_PATH}.QueueLogger"),
        ):
            mock_swap_service.create_swap = AsyncMock(return_value="swap_123")
            mock_swap_service.add_task_to_swap = AsyncMock()

            await request_swap(
                mock_context,
                mock_ctx,
                sample_members,
                mock_user,
                target_id="456",
            )

            # Проверяем, что ID были конвертированы в int
            call_kwargs = mock_swap_service.create_swap.call_args[1]
            assert call_kwargs["requester_id"] == 123
            assert call_kwargs["target_id"] == 456

    async def test_request_swap_members_without_user_id(self, mock_context, mock_user, mock_ctx):
        """Тест с членами без user_id."""
        members = [
            {"display_name": "Unknown"},
            {"user_id": 456, "display_name": "Bob"},
        ]
        with patch(f"{MODULE_PATH}.swap_service"):
            await request_swap(
                mock_context,
                mock_ctx,
                members,
                mock_user,
                target_id="456",
            )
            # Должно работать, пропуская member без user_id

    async def test_request_swap_positions_in_message(self, mock_context, mock_user, mock_ctx, sample_members):
        """Тест, что в сообщении указаны правильные позиции."""
        with (
            patch(f"{MODULE_PATH}.swap_service") as mock_swap_service,
            patch(f"{MODULE_PATH}.swap_confirmation_keyboard"),
            patch(f"{MODULE_PATH}.delete_message_later") as mock_delete_later,
            patch(f"{MODULE_PATH}.QueueLogger"),
        ):
            mock_swap_service.create_swap = AsyncMock(return_value="swap_123")
            mock_swap_service.add_task_to_swap = AsyncMock()

            await request_swap(
                mock_context,
                mock_ctx,
                sample_members,
                mock_user,
                target_id="456",  # Bob на позиции 2
            )

            # Проверяем текст сообщения
            call_args = mock_delete_later.call_args
            message_text = call_args[0][2]  # 3-й аргумент это text
            assert "Bob" in message_text
            assert "(2)" in message_text  # позиция 2
            assert "Alice" in message_text
            assert "(1)" in message_text  # позиция 1


@pytest.mark.asyncio
class TestRespondSwap:
    async def test_respond_swap_accept_success(self, mock_context, mock_user, mock_ctx):
        """Тест успешного принятия запроса на обмен."""
        # Настраиваем пользователя как Target (Bob), так как именно он принимает обмен
        mock_user.id = 456
        mock_user.first_name = "Bob"

        members = [
            {"user_id": 123, "display_name": "Alice"},
            {"user_id": 456, "display_name": "Bob"},
        ]
        queue = {"members": members}
        swap_data = {
            "requester_id": 123,
            "target_id": 456,
            "requester_name": "Alice",
            "target_name": "Bob",
        }

        with (
            patch(f"{MODULE_PATH}.swap_service") as mock_swap_service,
            patch(f"{MODULE_PATH}.queue_service") as mock_queue_service,
            patch(f"{MODULE_PATH}.delete_message_later") as mock_delete_later,
            patch(f"{MODULE_PATH}.QueueLogger") as mock_logger,
        ):
            mock_swap_service.get_swap = AsyncMock(return_value=swap_data)
            mock_swap_service.respond_swap = AsyncMock()
            mock_queue_service.repo.get_queue = AsyncMock(return_value=queue)
            mock_queue_service.repo.update_queue_members = AsyncMock()

            # ВАЖНО: Мокаем вызов получения имени пользователя
            mock_queue_service.user_service.get_user_display_name = AsyncMock(return_value="Bob")

            result = await respond_swap(mock_context, mock_ctx, mock_user, "swap_123", accept=True)

            assert result is True

            # Проверяем, что члены были поменяны
            called_members = mock_queue_service.repo.update_queue_members.call_args[0][2]
            assert called_members[0]["user_id"] == 456  # Bob теперь на позиции 0 (индекс 0 в списке)
            # Внимание: логика обмена местами зависит от реализации swap.
            # Обычно swap меняет местами элементы.
            # Alice (idx 0) <-> Bob (idx 1).
            # Ожидаем: Bob (idx 0), Alice (idx 1).
            assert called_members[0]["user_id"] == 456
            assert called_members[1]["user_id"] == 123

            # Проверяем логирование обмена
            mock_logger.replaced.assert_called_once()

    async def test_respond_swap_decline(self, mock_context, mock_user, mock_ctx):
        """Тест отклонения запроса на обмен."""
        # Пользователь должен быть Target (Bob)
        mock_user.id = 456

        swap_data = {
            "requester_id": 123,
            "target_id": 456,
            "requester_name": "Alice",
            "target_name": "Bob",
        }

        with (
            patch(f"{MODULE_PATH}.swap_service") as mock_swap_service,
            patch(f"{MODULE_PATH}.delete_message_later") as mock_delete_later,
            patch(f"{MODULE_PATH}.queue_service") as mock_queue_service,
        ):
            mock_swap_service.get_swap = AsyncMock(return_value=swap_data)
            mock_swap_service.respond_swap = AsyncMock()

            mock_queue_service.user_service.get_user_display_name = AsyncMock(return_value="Bob")

            result = await respond_swap(mock_context, mock_ctx, mock_user, "swap_123", accept=False)

            assert result is True
            mock_swap_service.respond_swap.assert_awaited_once()
            mock_delete_later.assert_awaited_once()

    async def test_respond_swap_not_found(self, mock_context, mock_user, mock_ctx):
        """Тест ответа на несуществующий swap."""
        with (
            patch(f"{MODULE_PATH}.swap_service") as mock_swap_service,
            patch(f"{MODULE_PATH}.delete_message_later") as mock_delete_later,
            patch(f"{MODULE_PATH}.queue_service"),
        ):
            mock_swap_service.get_swap = AsyncMock(return_value=None)

            result = await respond_swap(mock_context, mock_ctx, mock_user, "nonexistent", accept=True)

            assert result is True
            mock_delete_later.assert_awaited_once()

    async def test_respond_swap_wrong_user(self, mock_context, mock_user, mock_ctx):
        """Тест ответа от неправильного пользователя."""
        swap_data = {
            "requester_id": 123,
            "target_id": 456,
            "requester_name": "Alice",
            "target_name": "Bob",
        }

        with (
            patch(f"{MODULE_PATH}.swap_service") as mock_swap_service,
            patch(f"{MODULE_PATH}.delete_message_later") as mock_delete_later,
            patch(f"{MODULE_PATH}.queue_service") as mock_queue_service,
        ):
            mock_swap_service.get_swap = AsyncMock(return_value=swap_data)
            mock_queue_service.user_service.get_user_display_name = AsyncMock(return_value="Stranger")

            mock_user.id = 999  # Не целевой пользователь (target_id=456)

            result = await respond_swap(mock_context, mock_ctx, mock_user, "swap_123", accept=True)

            # Должно быть None, так как проверка user_id == target_id не прошла
            assert result is None

    async def test_respond_swap_requester_not_in_queue(self, mock_context, mock_user, mock_ctx):
        """Тест когда requester больше не в очереди."""
        # Пользователь - Target (Bob)
        mock_user.id = 456

        members = [
            {"user_id": 456, "display_name": "Bob"},
        ]
        queue = {"members": members}
        swap_data = {
            "requester_id": 123,
            "target_id": 456,
            "requester_name": "Alice",
            "target_name": "Bob",
        }

        with (
            patch(f"{MODULE_PATH}.swap_service") as mock_swap_service,
            patch(f"{MODULE_PATH}.queue_service") as mock_queue_service,
            patch(f"{MODULE_PATH}.delete_message_later") as mock_delete_later,
        ):
            mock_swap_service.get_swap = AsyncMock(return_value=swap_data)
            mock_queue_service.repo.get_queue = AsyncMock(return_value=queue)
            mock_swap_service.delete_swap = AsyncMock()

            mock_queue_service.user_service.get_user_display_name = AsyncMock(return_value="Bob")

            result = await respond_swap(mock_context, mock_ctx, mock_user, "swap_123", accept=True)

            # Должно быть обработано как ошибка (requester не найден)
            mock_delete_later.assert_awaited_once()
            mock_swap_service.delete_swap.assert_awaited_once()

    async def test_respond_swap_target_not_in_queue(self, mock_context, mock_user, mock_ctx):
        """Тест когда target больше не в очереди."""
        # Пользователь - Target (Bob)
        mock_user.id = 456

        members = [
            {"user_id": 123, "display_name": "Alice"},
        ]
        queue = {"members": members}
        swap_data = {
            "requester_id": 123,
            "target_id": 456,
            "requester_name": "Alice",
            "target_name": "Bob",
        }

        with (
            patch(f"{MODULE_PATH}.swap_service") as mock_swap_service,
            patch(f"{MODULE_PATH}.queue_service") as mock_queue_service,
            patch(f"{MODULE_PATH}.delete_message_later") as mock_delete_later,
        ):
            mock_swap_service.get_swap = AsyncMock(return_value=swap_data)
            mock_queue_service.repo.get_queue = AsyncMock(return_value=queue)
            mock_swap_service.delete_swap = AsyncMock()

            mock_queue_service.user_service.get_user_display_name = AsyncMock(return_value="Bob")

            result = await respond_swap(mock_context, mock_ctx, mock_user, "swap_123", accept=True)

            # Должно быть обработано как ошибка (target не найден)
            mock_delete_later.assert_awaited_once()
            mock_swap_service.delete_swap.assert_awaited_once()

    async def test_respond_swap_exception_during_update(self, mock_context, mock_user, mock_ctx):
        """Тест обработки исключения при обновлении очереди."""
        # Пользователь - Target (Bob)
        mock_user.id = 456

        members = [
            {"user_id": 123, "display_name": "Alice"},
            {"user_id": 456, "display_name": "Bob"},
        ]
        queue = {"members": members}
        swap_data = {
            "requester_id": 123,
            "target_id": 456,
            "requester_name": "Alice",
            "target_name": "Bob",
        }

        with (
            patch(f"{MODULE_PATH}.swap_service") as mock_swap_service,
            patch(f"{MODULE_PATH}.queue_service") as mock_queue_service,
            patch(f"{MODULE_PATH}.QueueLogger") as mock_logger,
        ):
            mock_swap_service.get_swap = AsyncMock(return_value=swap_data)
            mock_queue_service.repo.get_queue = AsyncMock(return_value=queue)
            mock_queue_service.repo.update_queue_members = AsyncMock(side_effect=Exception("Database error"))
            mock_swap_service.delete_swap = AsyncMock()

            mock_queue_service.user_service.get_user_display_name = AsyncMock(return_value="Bob")

            with pytest.raises(Exception, match="Database error"):
                await respond_swap(mock_context, mock_ctx, mock_user, "swap_123", accept=True)

            # Проверяем, что swap был удален
            mock_swap_service.delete_swap.assert_awaited_once()
            # Проверяем логирование ошибки
            mock_logger.log.assert_called_once()

    async def test_respond_swap_empty_members_list(self, mock_context, mock_user, mock_ctx):
        """Тест с пустым списком членов очереди."""
        # Пользователь - Target (Bob)
        mock_user.id = 456

        queue = {"members": []}
        swap_data = {
            "requester_id": 123,
            "target_id": 456,
            "requester_name": "Alice",
            "target_name": "Bob",
        }

        with (
            patch(f"{MODULE_PATH}.swap_service") as mock_swap_service,
            patch(f"{MODULE_PATH}.queue_service") as mock_queue_service,
            patch(f"{MODULE_PATH}.delete_message_later") as mock_delete_later,
        ):
            mock_swap_service.get_swap = AsyncMock(return_value=swap_data)
            mock_queue_service.repo.get_queue = AsyncMock(return_value=queue)
            mock_swap_service.delete_swap = AsyncMock()

            mock_queue_service.user_service.get_user_display_name = AsyncMock(return_value="Bob")

            result = await respond_swap(mock_context, mock_ctx, mock_user, "swap_123", accept=True)

            mock_delete_later.assert_awaited_once()

    async def test_respond_swap_members_without_user_id(self, mock_context, mock_user, mock_ctx):
        """Тест с членами, у которых нет user_id."""
        # Пользователь - Target (Bob)
        mock_user.id = 456

        members = [
            {"display_name": "Unknown"},
            {"user_id": 123, "display_name": "Alice"},
            {"user_id": 456, "display_name": "Bob"},
        ]
        queue = {"members": members}
        swap_data = {
            "requester_id": 123,
            "target_id": 456,
            "requester_name": "Alice",
            "target_name": "Bob",
        }

        with (
            patch(f"{MODULE_PATH}.swap_service") as mock_swap_service,
            patch(f"{MODULE_PATH}.queue_service") as mock_queue_service,
            patch(f"{MODULE_PATH}.delete_message_later") as mock_delete_later,
            patch(f"{MODULE_PATH}.QueueLogger"),
        ):
            mock_swap_service.get_swap = AsyncMock(return_value=swap_data)
            mock_queue_service.repo.get_queue = AsyncMock(return_value=queue)
            mock_queue_service.repo.update_queue_members = AsyncMock()
            mock_swap_service.respond_swap = AsyncMock()

            mock_queue_service.user_service.get_user_display_name = AsyncMock(return_value="Bob")

            result = await respond_swap(mock_context, mock_ctx, mock_user, "swap_123", accept=True)

            assert result is True

            # Проверяем, что обмен был выполнен с правильными индексами
            called_members = mock_queue_service.repo.update_queue_members.call_args[0][2]
            # В исходном списке: 0:Unknown, 1:Alice(123), 2:Bob(456)
            # Меняем местами Alice и Bob.
            # Ожидаем: 0:Unknown, 1:Bob(456), 2:Alice(123)
            assert called_members[1]["user_id"] == 456
            assert called_members[2]["user_id"] == 123
