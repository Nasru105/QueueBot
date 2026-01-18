# tests/test_queues_menu/test_queues_menu.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from telegram import Update, User, CallbackQuery, Message
from telegram.ext import ContextTypes

from app.queues.models import ActionContext
from app.queues_menu.queues_menu import handle_queues_menu


@pytest.mark.asyncio
class TestQueuesMenu:
    """Тесты для обработчика меню списка очередей."""

    @pytest.fixture
    def setup_common(self):
        """Подготовка общих объектов для тестов."""
        self.update = MagicMock(spec=Update)
        self.update.callback_query = MagicMock(spec=CallbackQuery)
        self.update.callback_query.answer = AsyncMock()
        self.update.callback_query.edit_message_text = AsyncMock()
        self.update.callback_query.message = MagicMock(spec=Message)
        self.update.callback_query.message.message_id = 12345

        self.context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        self.context.bot = AsyncMock()

        self.ctx = ActionContext(
            chat_id=123,
            chat_title="Test Chat",
            queue_id="test_queue",
            queue_name="",
            actor="test_user",
        )

        return {
            "update": self.update,
            "context": self.context,
            "ctx": self.ctx,
        }

    @pytest.mark.asyncio
    async def test_handle_queues_menu_get_action(self, setup_common):
        """Тест действия get для отображения очереди."""
        expiration_time = datetime(2025, 12, 31, 23, 59, 59)
        queue_data = {"name": "Priority Queue", "members": ["user1", "user2"]}

        with patch("app.queues_menu.queues_menu.queue_service") as mock_service:
            with patch("app.queues_menu.queues_menu.queue_menu_keyboard", new_callable=AsyncMock) as mock_keyboard:
                with patch("app.queues_menu.queues_menu.escape_markdown") as mock_escape:
                    mock_service.repo.get_queue = AsyncMock(return_value=queue_data)
                    mock_service.repo.get_queue_expiration = AsyncMock(return_value=expiration_time)
                    mock_keyboard.return_value = MagicMock()
                    mock_escape.return_value = "Escaped Text"

                    await handle_queues_menu(
                        setup_common["update"], setup_common["context"], setup_common["ctx"], "get"
                    )

                    setup_common["update"].callback_query.edit_message_text.assert_called_once()
                    call_kwargs = setup_common["update"].callback_query.edit_message_text.call_args[1]
                    assert call_kwargs["text"] == "Escaped Text"
                    assert call_kwargs["parse_mode"] == "MarkdownV2"

    @pytest.mark.asyncio
    async def test_handle_queues_menu_get_sets_queue_name(self, setup_common):
        """Тест что queue_name устанавливается при действии get."""
        queue_data = {"name": "Test Queue", "members": []}
        expiration_time = datetime(2025, 12, 31, 23, 59, 59)

        with patch("app.queues_menu.queues_menu.queue_service") as mock_service:
            with patch("app.queues_menu.queues_menu.queue_menu_keyboard", new_callable=AsyncMock):
                with patch("app.queues_menu.queues_menu.escape_markdown"):
                    mock_service.repo.get_queue = AsyncMock(return_value=queue_data)
                    mock_service.repo.get_queue_expiration = AsyncMock(return_value=expiration_time)

                    await handle_queues_menu(
                        setup_common["update"], setup_common["context"], setup_common["ctx"], "get"
                    )

                    assert setup_common["ctx"].queue_name == "Test Queue"

    @pytest.mark.asyncio
    async def test_handle_queues_menu_get_formats_expiration_date(self, setup_common):
        """Тест форматирования даты истечения очереди."""
        queue_data = {"name": "Test Queue", "members": []}
        expiration_time = datetime(2025, 6, 15, 14, 30, 45)

        with patch("app.queues_menu.queues_menu.queue_service") as mock_service:
            with patch("app.queues_menu.queues_menu.queue_menu_keyboard", new_callable=AsyncMock):
                with patch("app.queues_menu.queues_menu.escape_markdown") as mock_escape:
                    mock_service.repo.get_queue = AsyncMock(return_value=queue_data)
                    mock_service.repo.get_queue_expiration = AsyncMock(return_value=expiration_time)

                    await handle_queues_menu(
                        setup_common["update"], setup_common["context"], setup_common["ctx"], "get"
                    )

                    # Проверяем что escape_markdown вызван с правильной датой
                    mock_escape.assert_called_once()
                    called_text = mock_escape.call_args[0][0]
                    assert "15.06.2025 14:30:45" in called_text

    @pytest.mark.asyncio
    async def test_handle_queues_menu_hide_action(self, setup_common):
        """Тест действия hide для скрытия меню."""
        with patch("app.queues_menu.queues_menu.queue_service") as mock_service:
            mock_service.message_service.hide_queues_list_message = AsyncMock()

            await handle_queues_menu(setup_common["update"], setup_common["context"], setup_common["ctx"], "hide")

            mock_service.message_service.hide_queues_list_message.assert_called_once_with(
                setup_common["context"],
                setup_common["ctx"],
                12345,  # message_id
            )

    @pytest.mark.asyncio
    async def test_handle_queues_menu_hide_returns_early(self, setup_common):
        """Тест что действие hide возвращает функцию рано."""
        with patch("app.queues_menu.queues_menu.queue_service") as mock_service:
            mock_service.message_service.hide_queues_list_message = AsyncMock()

            result = await handle_queues_menu(
                setup_common["update"], setup_common["context"], setup_common["ctx"], "hide"
            )

            # Функция должна вернуть None (early return)
            assert result is None

    @pytest.mark.asyncio
    async def test_handle_queues_menu_get_with_different_queue_names(self, setup_common):
        """Тест работы с разными именами очередей."""
        expiration_time = datetime(2025, 12, 31, 23, 59, 59)

        for queue_name in ["Simple Queue", "Queue with spaces", "Очередь", "Q1"]:
            queue_data = {"name": queue_name, "members": []}

            with patch("app.queues_menu.queues_menu.queue_service") as mock_service:
                with patch("app.queues_menu.queues_menu.queue_menu_keyboard", new_callable=AsyncMock):
                    with patch("app.queues_menu.queues_menu.escape_markdown"):
                        mock_service.repo.get_queue = AsyncMock(return_value=queue_data)
                        mock_service.repo.get_queue_expiration = AsyncMock(return_value=expiration_time)

                        ctx = ActionContext(
                            chat_id=123,
                            chat_title="Test Chat",
                            queue_id="test_queue",
                            queue_name="",
                            actor="test_user",
                        )

                        await handle_queues_menu(setup_common["update"], setup_common["context"], ctx, "get")

                        assert ctx.queue_name == queue_name
