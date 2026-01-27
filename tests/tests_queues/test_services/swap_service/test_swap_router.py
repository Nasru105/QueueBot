from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Update

from app.queues.models import ActionContext, Member, Queue
from app.queues.services.swap_service.swap_router import swap_router

MODULE_PATH = "app.queues.services.swap_service.swap_router"


@pytest.fixture
def mock_update():
    """Создает мок Telegram Update с callback_query."""
    update = MagicMock(spec=Update)
    query = MagicMock()
    query.from_user = MagicMock()
    query.from_user.id = 123
    query.message = MagicMock()
    query.message.message_id = 555
    update.callback_query = query
    return update


@pytest.fixture
def mock_context(facade_service):
    """Создает мок Telegram контекста."""
    context = MagicMock()
    context.bot = AsyncMock()
    context.bot_data = {"queue_service": facade_service}
    return context


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
def sample_queue():
    """Создает пример очереди."""
    return Queue(
        id="test_queue",
        name="Test Queue",
        members=[
            Member(user_id=123, display_name="Alice"),
            Member(user_id=456, display_name="Bob"),
        ],
    )


@pytest.mark.asyncio
class TestSwapRouter:
    async def test_swap_router_request_action(self, facade_service, mock_update, mock_context, mock_ctx, sample_queue):
        """Тест обработки действия request (запрос на обмен)."""
        with (
            patch(f"{MODULE_PATH}.request_swap") as mock_request_swap,
        ):
            mock_request_swap.return_value = AsyncMock()
            # Настраиваем AsyncMock для вызываемого метода
            facade_service.message_service.hide_queues_list_message = AsyncMock()
            mock_context.bot.delete_message = AsyncMock()
            await swap_router(mock_update, mock_context, mock_ctx, sample_queue, args=["request", "456"])
            # Проверяем, что request_swap был вызван с правильными аргументами
            mock_request_swap.assert_awaited_once()
            call_args = mock_request_swap.call_args
            assert call_args[0][0] == mock_context
            assert call_args[0][1] == mock_ctx
            assert call_args[0][2] == sample_queue.members
            assert call_args[0][3] == mock_update.callback_query.from_user
            assert call_args[0][4] == "456"
            # Проверяем, что список был скрыт
            mock_context.bot.delete_message.assert_awaited_once_with(chat_id=999, message_id=555)

    async def test_swap_router_accept_action(self, facade_service, mock_update, mock_context, mock_ctx, sample_queue):
        """Тест обработки действия accept (принятие обмена)."""
        with (
            patch(f"{MODULE_PATH}.respond_swap") as mock_respond_swap,
        ):
            mock_respond_swap.return_value = AsyncMock(return_value=True)()
            facade_service.update_queue_message = AsyncMock()
            await swap_router(mock_update, mock_context, mock_ctx, sample_queue, args=["accept", "swap_123"])
            # Проверяем, что respond_swap был вызван с accept=True
            mock_respond_swap.assert_awaited_once()
            call_args = mock_respond_swap.call_args
            # Индекс 3, т.к. аргументы: context, ctx, user, swap_id
            assert call_args[0][3] == "swap_123"
            assert call_args[1]["accept"] is True
            # Проверяем обновление сообщения
            facade_service.update_queue_message.assert_awaited_once_with(mock_context, mock_ctx)
            # Проверяем удаление сообщения
            mock_context.bot.delete_message.assert_awaited_once_with(chat_id=999, message_id=555)

    async def test_swap_router_decline_action(self, facade_service, mock_update, mock_context, mock_ctx, sample_queue):
        """Тест обработки действия decline (отклонение обмена)."""
        with patch(f"{MODULE_PATH}.respond_swap") as mock_respond_swap:
            mock_respond_swap.return_value = AsyncMock(return_value=True)()
            await swap_router(mock_update, mock_context, mock_ctx, sample_queue, args=["decline", "swap_123"])
            # Проверяем, что respond_swap был вызван с accept=False
            mock_respond_swap.assert_awaited_once()
            call_args = mock_respond_swap.call_args
            # Индекс 3, т.к. аргументы: context, ctx, user, swap_id
            assert call_args[0][3] == "swap_123"
            assert call_args[1]["accept"] is False
            # Проверяем удаление сообщения
            mock_context.bot.delete_message.assert_awaited_once_with(chat_id=999, message_id=555)

    async def test_swap_router_no_target(self, facade_service, mock_update, mock_context, mock_ctx, sample_queue):
        """Тест с отсутствующим target параметром."""
        with (
            patch(f"{MODULE_PATH}.request_swap") as mock_request_swap,
            patch(f"{MODULE_PATH}.respond_swap") as mock_respond_swap,
        ):
            # Настраиваем моки
            facade_service.message_service.hide_queues_list_message = AsyncMock()
            # request с пустым target
            await swap_router(mock_update, mock_context, mock_ctx, sample_queue, args=["request", ""])
            # Ничего не должно произойти
            mock_request_swap.assert_not_awaited()
            mock_respond_swap.assert_not_awaited()
            mock_context.bot.delete_message.assert_not_awaited()

    async def test_swap_router_accept_still_deletes_when_false(
        self, facade_service, mock_update, mock_context, mock_ctx, sample_queue
    ):
        """Тест, что сообщение не удаляется если respond_swap вернул False (очистка меню)."""
        with (
            patch(f"{MODULE_PATH}.respond_swap") as mock_respond_swap,
        ):
            facade_service.update_queue_message = AsyncMock()
            mock_respond_swap.return_value = False
            await swap_router(mock_update, mock_context, mock_ctx, sample_queue, args=["accept", "swap_123"])
            # Сообщение ДОЛЖНО быть удалено (меню убирается после действия)
            mock_context.bot.delete_message.assert_not_awaited()

    async def test_swap_router_decline_still_deletes_when_false(
        self, facade_service, mock_update, mock_context, mock_ctx, sample_queue
    ):
        """Тест, что сообщение удаляется даже если respond_swap вернул False для decline."""
        with patch(f"{MODULE_PATH}.respond_swap") as mock_respond_swap:
            mock_respond_swap.return_value = AsyncMock(return_value=False)()
            await swap_router(mock_update, mock_context, mock_ctx, sample_queue, args=["decline", "swap_123"])
            # Сообщение ДОЛЖНО быть удалено
            mock_context.bot.delete_message.assert_awaited_once()

    async def test_swap_router_empty_members(self, facade_service, mock_update, mock_context, mock_ctx):
        """Тест с пустым списком членов."""
        queue = Queue(id="test_queue", name="Test Queue", members=[])
        with (
            patch(f"{MODULE_PATH}.request_swap") as mock_request_swap,
        ):
            mock_request_swap.return_value = AsyncMock()
            facade_service.message_service.hide_queues_list_message = AsyncMock()
            await swap_router(mock_update, mock_context, mock_ctx, queue, args=["request", "456"])
            # Должен быть вызван request_swap с пустым списком
            mock_request_swap.assert_awaited_once()

    async def test_swap_router_queue_without_members_key(self, facade_service, mock_update, mock_context, mock_ctx):
        """Тест с очередью без ключа members."""
        queue = Queue(id="test_queue", name="Test Queue")
        with (
            patch(f"{MODULE_PATH}.request_swap") as mock_request_swap,
        ):
            mock_request_swap.return_value = AsyncMock()
            facade_service.message_service.hide_queues_list_message = AsyncMock()
            await swap_router(mock_update, mock_context, mock_ctx, queue, args=["request", "456"])
            # members должны быть пусты (default=[])
            call_args = mock_request_swap.call_args
            assert call_args[0][2] == []

    async def test_swap_router_unknown_action(self, facade_service, mock_update, mock_context, mock_ctx, sample_queue):
        """Тест с неизвестным действием."""
        with (
            patch(f"{MODULE_PATH}.request_swap") as mock_request_swap,
            patch(f"{MODULE_PATH}.respond_swap") as mock_respond_swap,
        ):
            await swap_router(mock_update, mock_context, mock_ctx, sample_queue, args=["unknown", "target"])
            # Ничего не должно произойти
            mock_request_swap.assert_not_awaited()
            mock_respond_swap.assert_not_awaited()

    async def test_swap_router_request_update_queue_message_not_called(
        self, facade_service, mock_update, mock_context, mock_ctx, sample_queue
    ):
        """Тест что update_queue_message не вызывается для request."""
        with (
            patch(f"{MODULE_PATH}.request_swap") as mock_request_swap,
        ):
            mock_request_swap.return_value = AsyncMock()
            facade_service.message_service.hide_queues_list_message = AsyncMock()
            facade_service.update_queue_message = AsyncMock()
            await swap_router(mock_update, mock_context, mock_ctx, sample_queue, args=["request", "456"])
            # update_queue_message должен быть вызван только для accept
            facade_service.update_queue_message.assert_not_awaited()

    async def test_swap_router_accept_deletes_message_on_true(
        self, facade_service, mock_update, mock_context, mock_ctx, sample_queue
    ):
        """Тест удаления сообщения при успешном accept."""
        with (
            patch(f"{MODULE_PATH}.respond_swap") as mock_respond_swap,
        ):
            mock_respond_swap.return_value = AsyncMock(return_value=True)()
            facade_service.update_queue_message = AsyncMock()
            await swap_router(mock_update, mock_context, mock_ctx, sample_queue, args=["accept", "swap_123"])
            # Сообщение должно быть удалено
            mock_context.bot.delete_message.assert_awaited_once()
            call_args = mock_context.bot.delete_message.call_args
            assert call_args[1]["chat_id"] == 999
            assert call_args[1]["message_id"] == 555

    async def test_swap_router_multiple_args(self, facade_service, mock_update, mock_context, mock_ctx, sample_queue):
        """Тест обработки при наличии дополнительных аргументов (вызывает ошибку распаковки)."""
        with (
            patch(f"{MODULE_PATH}.request_swap") as mock_request_swap,
        ):
            # Проверяем, что код строго требует 2 аргумента
            with pytest.raises(ValueError, match="too many values to unpack"):
                await swap_router(
                    mock_update,
                    mock_context,
                    mock_ctx,
                    sample_queue,
                    args=["request", "456", "extra", "args"],
                )

    async def test_swap_router_decline_with_return_none(
        self, facade_service, mock_update, mock_context, mock_ctx, sample_queue
    ):
        """Тест decline когда respond_swap возвращает None."""
        with patch(f"{MODULE_PATH}.respond_swap") as mock_respond_swap:
            mock_respond_swap.return_value = AsyncMock(return_value=None)()
            await swap_router(mock_update, mock_context, mock_ctx, sample_queue, args=["decline", "swap_123"])
            # Сообщение должно быть удалено (очистка меню)
            mock_context.bot.delete_message.assert_awaited_once()
