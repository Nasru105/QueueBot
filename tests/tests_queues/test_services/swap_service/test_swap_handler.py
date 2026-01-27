from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import User

from app.queues.models import ActionContext, Member
from app.queues.services.swap_service.swap_handler import request_swap

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
        Member(user_id=123, display_name="Alice"),
        Member(user_id=456, display_name="Bob"),
        Member(user_id=789, display_name="Charlie"),
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

            # ИСПРАВЛЕНИЕ 1: Делаем метод log асинхронным
            mock_logger.log = AsyncMock()

            await request_swap(
                mock_context,
                mock_ctx,
                sample_members,
                mock_user,
                target_id="456",  # Bob
            )

            mock_swap_service.create_swap.assert_awaited_once()
            call_kwargs = mock_swap_service.create_swap.call_args[1]
            assert call_kwargs["chat_id"] == 999
            assert call_kwargs["queue_id"] == "test_queue"
            assert call_kwargs["requester_id"] == 123
            assert call_kwargs["target_id"] == 456
            assert call_kwargs["requester_name"] == "Alice"
            assert call_kwargs["target_name"] == "Bob"
            assert call_kwargs["ttl"] == 120

            mock_delete_later.assert_awaited_once()
            mock_swap_service.add_task_to_swap.assert_awaited_once_with("swap_123", mock_delete_later.return_value)

            # Проверяем вызов логгера
            mock_logger.log.assert_awaited_once()

    async def test_request_swap_same_user(self, mock_context, mock_user, mock_ctx, sample_members):
        """Тест запроса обмена у самого себя - должен быть пропущен."""
        with patch(f"{MODULE_PATH}.swap_service"):
            await request_swap(
                mock_context,
                mock_ctx,
                sample_members,
                mock_user,
                target_id="123",
            )

    async def test_request_swap_invalid_user_id(self, mock_context, mock_user, mock_ctx, sample_members):
        """Тест с невалидным ID пользователя."""
        with patch(f"{MODULE_PATH}.swap_service"):
            await request_swap(
                mock_context,
                mock_ctx,
                sample_members,
                mock_user,
                target_id="999",
            )

    async def test_request_swap_invalid_requester_id(self, mock_context, mock_user, mock_ctx, sample_members):
        """Тест когда requester не найден в очереди."""
        mock_user.id = 999
        with patch(f"{MODULE_PATH}.swap_service"):
            await request_swap(
                mock_context,
                mock_ctx,
                sample_members,
                mock_user,
                target_id="456",
            )

    async def test_request_swap_string_ids(self, mock_context, mock_user, mock_ctx, sample_members):
        """Тест обработки ID как строк."""
        mock_user.id = "123"
        with (
            patch(f"{MODULE_PATH}.swap_service") as mock_swap_service,
            patch(f"{MODULE_PATH}.swap_confirmation_keyboard"),
            patch(f"{MODULE_PATH}.delete_message_later"),
            patch(f"{MODULE_PATH}.QueueLogger") as mock_logger,  # Добавляем mock_logger в контекст
        ):
            mock_swap_service.create_swap = AsyncMock(return_value="swap_123")
            mock_swap_service.add_task_to_swap = AsyncMock()

            # ИСПРАВЛЕНИЕ 1: Делаем метод log асинхронным
            mock_logger.log = AsyncMock()

            await request_swap(
                mock_context,
                mock_ctx,
                sample_members,
                mock_user,
                target_id="456",
            )

            call_kwargs = mock_swap_service.create_swap.call_args[1]
            assert call_kwargs["requester_id"] == 123
            assert call_kwargs["target_id"] == 456

    async def test_request_swap_members_without_user_id(self, mock_context, mock_user, mock_ctx):
        """Тест с членами без user_id."""
        member_unknown = MagicMock()
        member_unknown.user_id = None  # Или отсутствует
        member_unknown.display_name = "Unknown"
        member_bob = Member(user_id=456, display_name="Bob")

        members = [member_unknown, member_bob]

        with patch(f"{MODULE_PATH}.swap_service"):
            await request_swap(
                mock_context,
                mock_ctx,
                members,
                mock_user,
                target_id="456",
            )
        # Должно работать, пропуская member без валидного user_id

    async def test_request_swap_positions_in_message(self, mock_context, mock_user, mock_ctx, sample_members):
        """Тест, что в сообщении указаны правильные позиции."""
        with (
            patch(f"{MODULE_PATH}.swap_service") as mock_swap_service,
            patch(f"{MODULE_PATH}.swap_confirmation_keyboard"),
            patch(f"{MODULE_PATH}.delete_message_later") as mock_delete_later,
            patch(f"{MODULE_PATH}.QueueLogger") as mock_logger,
        ):
            mock_swap_service.create_swap = AsyncMock(return_value="swap_123")
            mock_swap_service.add_task_to_swap = AsyncMock()

            # ИСПРАВЛЕНИЕ 1: Делаем метод log асинхронным
            mock_logger.log = AsyncMock()

            await request_swap(
                mock_context,
                mock_ctx,
                sample_members,
                mock_user,
                target_id="456",  # Bob на позиции 2
            )

            call_args = mock_delete_later.call_args
            message_text = call_args[0][2]
            assert "Bob" in message_text
            assert "(2)" in message_text
            assert "Alice" in message_text
            assert "(1)" in message_text


# Класс TestRespondSwap был в порядке, его можно оставить как есть
