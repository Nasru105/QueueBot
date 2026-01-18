# tests/test_queues_menu/test_queue_menu.py

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Message, Update
from telegram.ext import ContextTypes

from app.queues.models import ActionContext
from app.queues_menu.queue_menu import handle_queue_menu


@pytest.mark.asyncio
class TestQueueMenu:
    """Тесты для обработчика меню очереди."""

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
            queue_name="Test Queue",
            actor="test_user",
        )

        return {
            "update": self.update,
            "context": self.context,
            "ctx": self.ctx,
        }

    @pytest.mark.asyncio
    async def test_handle_queue_menu_refresh_action(self, setup_common):
        """Тест действия refresh в меню очереди."""
        with patch("app.queues_menu.queue_menu.queue_service") as mock_service:
            mock_service.send_queue_message = AsyncMock()
            mock_service.message_service.hide_queues_list_message = AsyncMock()
            mock_service.repo.get_queue = AsyncMock()

            await handle_queue_menu(setup_common["update"], setup_common["context"], setup_common["ctx"], "refresh")

            mock_service.send_queue_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_queue_menu_swap_action(self, setup_common):
        """Тест действия swap в меню очереди."""
        queue_data = {"name": "Test Queue", "members": ["user1", "user2", "user3"]}

        with patch("app.queues_menu.queue_menu.queue_service") as mock_service:
            with patch("app.queues_menu.queue_menu.queue_swap_keyboard", new_callable=AsyncMock) as mock_keyboard:
                mock_service.repo.get_queue = AsyncMock(return_value=queue_data)
                mock_keyboard.return_value = MagicMock()

                await handle_queue_menu(setup_common["update"], setup_common["context"], setup_common["ctx"], "swap")

                # Проверяем что вызван edit_message_text с правильным текстом
                setup_common["update"].callback_query.edit_message_text.assert_called_once()
                call_kwargs = setup_common["update"].callback_query.edit_message_text.call_args[1]
                assert "Отправить запрос на обмен местом" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_handle_queue_menu_delete_action(self, setup_common):
        """Тест действия delete в меню очереди."""
        queue_data = {"name": "Test Queue", "members": []}

        with patch("app.queues_menu.queue_menu.queue_service") as mock_service:
            with patch("app.queues_menu.queue_menu.safe_delete", new_callable=AsyncMock) as mock_safe_delete:
                mock_service.repo.get_queue = AsyncMock(return_value=queue_data)
                mock_service.repo.get_queue_message_id = AsyncMock(return_value=67890)
                mock_service.delete_queue = AsyncMock()
                mock_service.message_service.hide_queues_list_message = AsyncMock()

                await handle_queue_menu(setup_common["update"], setup_common["context"], setup_common["ctx"], "delete")

                mock_safe_delete.assert_called_once()
                mock_service.delete_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_queue_menu_back_action(self, setup_common):
        """Тест действия back в меню очереди."""
        queue_data = {"name": "Test Queue", "members": []}
        queues_data = {
            "q1": {"name": "Queue 1"},
            "q2": {"name": "Queue 2"},
        }

        with patch("app.queues_menu.queue_menu.queue_service") as mock_service:
            with patch("app.queues_menu.queue_menu.queues_menu_keyboard", new_callable=AsyncMock) as mock_keyboard:
                mock_service.repo.get_queue = AsyncMock(return_value=queue_data)
                mock_service.repo.get_all_queues = AsyncMock(return_value=queues_data)
                mock_keyboard.return_value = MagicMock()

                await handle_queue_menu(setup_common["update"], setup_common["context"], setup_common["ctx"], "back")

                setup_common["update"].callback_query.edit_message_text.assert_called_once()
                call_kwargs = setup_common["update"].callback_query.edit_message_text.call_args[1]
                assert call_kwargs["text"] == "Список очередей"

    @pytest.mark.asyncio
    async def test_handle_queue_menu_queue_not_found(self, setup_common):
        """Тест когда очередь не найдена."""
        with patch("app.queues_menu.queue_menu.queue_service") as mock_service:
            with patch("app.queues_menu.queue_menu.delete_message_later", new_callable=AsyncMock) as mock_delete:
                mock_service.repo.get_queue = AsyncMock(return_value=None)

                await handle_queue_menu(setup_common["update"], setup_common["context"], setup_common["ctx"], "refresh")

                mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_queue_menu_sets_queue_name(self, setup_common):
        """Тест что queue_name корректно устанавливается."""
        queue_data = {"name": "My Special Queue", "members": []}

        with patch("app.queues_menu.queue_menu.queue_service") as mock_service:
            mock_service.repo.get_queue = AsyncMock(return_value=queue_data)
            mock_service.send_queue_message = AsyncMock()
            mock_service.message_service.hide_queues_list_message = AsyncMock()

            await handle_queue_menu(setup_common["update"], setup_common["context"], setup_common["ctx"], "refresh")

            assert setup_common["ctx"].queue_name == "My Special Queue"

    @pytest.mark.asyncio
    async def test_handle_queue_menu_with_empty_members(self, setup_common):
        """Тест обработки очереди без членов."""
        queue_data = {"name": "Empty Queue"}

        with patch("app.queues_menu.queue_menu.queue_service") as mock_service:
            with patch("app.queues_menu.queue_menu.queue_swap_keyboard", new_callable=AsyncMock) as mock_keyboard:
                mock_service.repo.get_queue = AsyncMock(return_value=queue_data)
                mock_keyboard.return_value = MagicMock()

                await handle_queue_menu(setup_common["update"], setup_common["context"], setup_common["ctx"], "swap")

                # Проверяем что keyboard вызван с пустым списком членов
                mock_keyboard.assert_called_once_with([], setup_common["ctx"].queue_id)
