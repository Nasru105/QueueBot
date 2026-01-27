import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Message, Update
from telegram.ext import ContextTypes

# Импортируем модуль целиком, чтобы перезагружать его
import app.queues_menu.router as router_module
from app.queues.errors import QueueError
from app.queues.models import ActionContext


@pytest.fixture
def bypass_decorator(mocker):
    """
    Отключаем декоратор @with_ctx, чтобы тесты могли передавать мок ctx напрямую,
    не вызывая конфликта аргументов (TypeError: multiple values for argument 'ctx').
    """
    mocker.patch("app.utils.utils.with_ctx", side_effect=lambda func: func)
    importlib.reload(router_module)
    return router_module


@pytest.mark.asyncio
class TestMenuRouter:
    """Тесты для роутера меню."""

    @pytest.fixture
    def setup_common(self):
        """Подготовка общих объектов для тестов."""
        self.update = MagicMock(spec=Update)
        self.update.callback_query = MagicMock(spec=CallbackQuery)
        self.update.callback_query.answer = AsyncMock()
        self.update.callback_query.data = "menu|queue|123|refresh"
        self.update.callback_query.message = MagicMock(spec=Message)
        self.update.callback_query.message.message_id = 12345
        self.context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        self.context.bot = AsyncMock()

        # Добавляем thread_id, так как он есть в определении модели
        self.ctx = ActionContext(
            chat_id=123, chat_title="Test Chat", queue_id="", queue_name="", actor="test_user", thread_id=None
        )
        return {
            "update": self.update,
            "context": self.context,
            "ctx": self.ctx,
        }

    async def test_menu_router_parses_queue_callback(self, setup_common, bypass_decorator):
        """Тест парсинга callback для очереди."""
        setup_common["update"].callback_query.data = "menu|queue|456|refresh"

        # Используем функцию из перезагруженного модуля (bypass_decorator)
        with patch("app.queues_menu.router.handle_queue_menu", new_callable=AsyncMock) as mock_handler:
            await bypass_decorator.menu_router(setup_common["update"], setup_common["context"], ctx=setup_common["ctx"])

            assert setup_common["ctx"].queue_id == "456"
            mock_handler.assert_called_once()

    async def test_menu_router_parses_queues_callback(self, setup_common, bypass_decorator):
        """Тест парсинга callback для списка очередей."""
        setup_common["update"].callback_query.data = "menu|queues|all|hide"
        with patch("app.queues_menu.router.handle_queues_menu", new_callable=AsyncMock) as mock_handler:
            await bypass_decorator.menu_router(setup_common["update"], setup_common["context"], ctx=setup_common["ctx"])

            assert setup_common["ctx"].queue_id == "all"
            mock_handler.assert_called_once()

    async def test_menu_router_dispatches_to_queue_handler(self, setup_common, bypass_decorator):
        """Тест диспетчеризации к обработчику очереди."""
        setup_common["update"].callback_query.data = "menu|queue|789|delete"
        with patch("app.queues_menu.router.handle_queue_menu", new_callable=AsyncMock) as mock_queue_handler:
            with patch("app.queues_menu.router.handle_queues_menu", new_callable=AsyncMock) as mock_queues_handler:
                await bypass_decorator.menu_router(
                    setup_common["update"], setup_common["context"], ctx=setup_common["ctx"]
                )

                mock_queue_handler.assert_called_once()
                mock_queues_handler.assert_not_called()

    async def test_menu_router_dispatches_to_queues_handler(self, setup_common, bypass_decorator):
        """Тест диспетчеризации к обработчику списка очередей."""
        setup_common["update"].callback_query.data = "menu|queues|q1|get"
        with patch("app.queues_menu.router.handle_queue_menu", new_callable=AsyncMock) as mock_queue_handler:
            with patch("app.queues_menu.router.handle_queues_menu", new_callable=AsyncMock) as mock_queues_handler:
                await bypass_decorator.menu_router(
                    setup_common["update"], setup_common["context"], ctx=setup_common["ctx"]
                )

                mock_queue_handler.assert_not_called()
                mock_queues_handler.assert_called_once()

    async def test_menu_router_invalid_callback_format(self, setup_common, bypass_decorator):
        """Тест обработки некорректного формата callback."""
        setup_common["update"].callback_query.data = "invalid_data"
        with patch("app.queues_menu.router.QueueLogger") as mock_logger:
            await bypass_decorator.menu_router(setup_common["update"], setup_common["context"], ctx=setup_common["ctx"])

            mock_logger.log.assert_called_once()
            call_kwargs = mock_logger.log.call_args[1]
            assert call_kwargs["level"] == "WARNING"

    async def test_menu_router_insufficient_callback_parts(self, setup_common, bypass_decorator):
        """Тест callback с недостаточным количеством частей."""
        setup_common["update"].callback_query.data = "menu|queue"
        with patch("app.queues_menu.router.QueueLogger") as mock_logger:
            await bypass_decorator.menu_router(setup_common["update"], setup_common["context"], ctx=setup_common["ctx"])

            mock_logger.log.assert_called_once()

    async def test_menu_router_unknown_menu_type(self, setup_common, bypass_decorator):
        """Тест обработки неизвестного типа меню."""
        setup_common["update"].callback_query.data = "menu|unknown|123|action"
        with patch("app.queues_menu.router.QueueLogger") as mock_logger:
            await bypass_decorator.menu_router(setup_common["update"], setup_common["context"], ctx=setup_common["ctx"])

            mock_logger.log.assert_called_once()
            call_args = mock_logger.log.call_args[0]
            assert "Unknown menu type" in call_args[1]

    async def test_menu_router_handles_queue_error(self, setup_common, bypass_decorator):
        """Тест обработки QueueError."""
        setup_common["update"].callback_query.data = "menu|queue|123|refresh"

        # Мокируем handle_queue_menu, чтобы он выбрасывал ошибку
        with patch("app.queues_menu.router.handle_queue_menu", new_callable=AsyncMock) as mock_handler:
            mock_handler.side_effect = QueueError("Test error")

            # Мокируем queue_service внутри context.bot_data
            mock_queue_service = AsyncMock()
            mock_queue_service.message_service.hide_queues_list_message = AsyncMock()

            # Подменяем bot_data в контексте
            setup_common["context"].bot_data = {"queue_service": mock_queue_service}

            await bypass_decorator.menu_router(setup_common["update"], setup_common["context"], ctx=setup_common["ctx"])

            # Проверяем, что метод был вызван
            mock_queue_service.message_service.hide_queues_list_message.assert_called_once()

    async def test_menu_router_extracts_queue_id_correctly(self, setup_common, bypass_decorator):
        """Тест корректного извлечения queue_id."""
        queue_ids = ["q1", "queue_123", "test-queue", "456"]
        for queue_id in queue_ids:
            setup_common["update"].callback_query.data = f"menu|queue|{queue_id}|refresh"
            with patch("app.queues_menu.router.handle_queue_menu", new_callable=AsyncMock):
                # Создаем новый ctx каждый раз для чистоты теста
                ctx = ActionContext(
                    chat_id=123, chat_title="Test", queue_id="", queue_name="", actor="user", thread_id=None
                )
                await bypass_decorator.menu_router(setup_common["update"], setup_common["context"], ctx=ctx)
                assert ctx.queue_id == queue_id

    async def test_menu_router_calls_answer(self, setup_common, bypass_decorator):
        """Тест что вызывается answer для callback_query."""
        setup_common["update"].callback_query.data = "menu|queue|123|refresh"
        with patch("app.queues_menu.router.handle_queue_menu", new_callable=AsyncMock):
            await bypass_decorator.menu_router(setup_common["update"], setup_common["context"], ctx=setup_common["ctx"])

            setup_common["update"].callback_query.answer.assert_called_once()

    async def test_menu_router_all_action_types(self, setup_common, bypass_decorator):
        """Тест обработки всех типов действий для очереди."""
        actions = ["refresh", "swap", "delete", "back"]
        for action in actions:
            setup_common["update"].callback_query.data = f"menu|queue|123|{action}"
            with patch("app.queues_menu.router.handle_queue_menu", new_callable=AsyncMock) as mock_handler:
                await bypass_decorator.menu_router(
                    setup_common["update"], setup_common["context"], ctx=setup_common["ctx"]
                )

                assert mock_handler.call_args[0][3] == action
