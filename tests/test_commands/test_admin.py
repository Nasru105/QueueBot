import importlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Chat, Message, Update, User
from telegram.ext import ContextTypes

import app.commands.admin as admin_module


@pytest.fixture
def admin_mocks(mocker):
    """
    Патчим ИСТОЧНИКИ зависимостей, чтобы при перезагрузке модуля
    он импортировал уже готовые моки.
    """
    # 1. Патчим декоратор with_ctx, чтобы передавать свой ctx
    mocker.patch("app.utils.utils.with_ctx", side_effect=lambda func: func)

    # 2. Патчим проверку прав (для декоратора admins_only)
    mock_is_admin = mocker.patch("app.utils.utils.is_user_admin", new_callable=AsyncMock)
    mock_is_admin.return_value = True

    # 3. Патчим утилиты
    mock_delete_later = mocker.patch("app.utils.utils.delete_message_later", new_callable=AsyncMock)
    mock_safe_delete = mocker.patch("app.utils.utils.safe_delete", new_callable=AsyncMock)

    # 4. Патчим ArgumentParser
    mock_parser = mocker.patch("app.services.argument_parser.ArgumentParser", autospec=True)

    # 5. Патчим QueueService
    mock_service = mocker.patch("app.queues.queue_service", autospec=True)

    # Настраиваем методы сервиса
    mock_service.repo = MagicMock()
    mock_service.repo.get_queue_by_name = AsyncMock()
    mock_service.repo.get_queue_message_id = AsyncMock()
    mock_service.repo.get_all_queues = AsyncMock()
    mock_service.repo.get_list_message_id = AsyncMock()
    mock_service.repo.clear_list_message_id = AsyncMock()

    mock_service.delete_queue = AsyncMock()
    mock_service.insert_into_queue = AsyncMock()
    mock_service.update_queue_message = AsyncMock()
    mock_service.remove_from_queue = AsyncMock()
    mock_service.replace_users_queue = AsyncMock()
    mock_service.rename_queue = AsyncMock()
    mock_service.set_queue_description = AsyncMock()

    mock_service.auto_cleanup_service = MagicMock()
    mock_service.auto_cleanup_service.reschedule_expiration = AsyncMock()

    # ВАЖНО: Перезагружаем модуль, чтобы он подтянул наши запатченные зависимости
    importlib.reload(admin_module)

    return {
        "service": mock_service,
        "parser": mock_parser,
        "delete_later": mock_delete_later,
        "safe_delete": mock_safe_delete,
        "is_admin": mock_is_admin,
    }


@pytest.mark.asyncio
class TestAdminCommands:
    @pytest.fixture(autouse=True)
    def setup_common(self):
        self.update = MagicMock(spec=Update)
        self.update.effective_user = MagicMock(spec=User)
        self.update.effective_chat = MagicMock(spec=Chat)
        # Для admins_only нужен title, иначе он считает это личным чатом
        self.update.effective_chat.title = "Test Group"
        self.update.message = MagicMock(spec=Message)

        self.context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        self.context.bot = AsyncMock()
        self.context.args = []

        self.ctx = MagicMock()
        self.ctx.chat_id = 123
        self.ctx.queue_name = None
        self.ctx.queue_id = None

    # ----------------------------------------------------------------
    # /delete
    # ----------------------------------------------------------------
    async def test_delete_queue_success(self, admin_mocks):
        self.context.args = ["My", "Queue"]

        # Мок поиска очереди
        admin_mocks["service"].repo.get_queue_by_name.return_value = {"id": "q1", "name": "My Queue"}
        admin_mocks["service"].repo.get_queue_message_id.return_value = 999

        # Вызываем функцию из перезагруженного модуля
        await admin_module.delete_queue(self.update, self.context, ctx=self.ctx)

        # Проверки
        assert self.ctx.queue_id == "q1"
        admin_mocks["safe_delete"].assert_awaited_once_with(self.context.bot, self.ctx, 999)
        admin_mocks["service"].delete_queue.assert_awaited_once_with(self.context, self.ctx)

    async def test_delete_queue_not_found(self, admin_mocks):
        self.context.args = ["Unknown"]
        admin_mocks["service"].repo.get_queue_by_name.return_value = None

        await admin_module.delete_queue(self.update, self.context, ctx=self.ctx)

        admin_mocks["delete_later"].assert_awaited_once()
        assert "не найдена" in admin_mocks["delete_later"].call_args[0][2]
        admin_mocks["service"].delete_queue.assert_not_awaited()

    async def test_delete_queue_no_args(self, admin_mocks):
        self.context.args = []
        await admin_module.delete_queue(self.update, self.context, ctx=self.ctx)

        admin_mocks["delete_later"].assert_awaited_once()
        assert "Использование" in admin_mocks["delete_later"].call_args[0][2]

    # ----------------------------------------------------------------
    # /delete_all_queues
    # ----------------------------------------------------------------
    async def test_delete_all_queues(self, admin_mocks):
        admin_mocks["service"].repo.get_list_message_id.return_value = 100
        admin_mocks["service"].repo.get_all_queues.return_value = {
            "q1": {"id": "q1", "name": "One"},
            "q2": {"id": "q2", "name": "Two"},
        }
        # get_queue_message_id вызывается 2 раза (для q1 и q2)
        admin_mocks["service"].repo.get_queue_message_id.side_effect = [101, 102]

        await admin_module.delete_all_queues(self.update, self.context, ctx=self.ctx)

        # Удаление главного меню
        admin_mocks["safe_delete"].assert_any_await(self.context.bot, self.ctx, 100)
        admin_mocks["service"].repo.clear_list_message_id.assert_awaited_once()

        # Удаление очередей (2 раза)
        assert admin_mocks["service"].delete_queue.await_count == 2

        # Проверяем, что сообщения очередей удалялись
        admin_mocks["safe_delete"].assert_any_await(self.context.bot, self.ctx, 101)
        admin_mocks["safe_delete"].assert_any_await(self.context.bot, self.ctx, 102)

    # ----------------------------------------------------------------
    # /insert
    # ----------------------------------------------------------------
    async def test_insert_user_success(self, admin_mocks):
        self.context.args = ["Queue", "User", "1"]
        admin_mocks["parser"].parse_queue_name.return_value = ("q1", "Queue", ["User", "1"])
        admin_mocks["parser"].parse_insert_args.return_value = ("User", 1)

        await admin_module.insert_user(self.update, self.context, ctx=self.ctx)

        admin_mocks["service"].insert_into_queue.assert_awaited_once_with(self.ctx, "User", 1)
        admin_mocks["service"].update_queue_message.assert_awaited_once()

    async def test_insert_user_queue_missing(self, admin_mocks):
        self.context.args = ["Unknown", "User"]
        admin_mocks["parser"].parse_queue_name.return_value = (None, None, [])

        await admin_module.insert_user(self.update, self.context, ctx=self.ctx)

        admin_mocks["delete_later"].assert_awaited_once()
        assert "Очередь не найдена" in admin_mocks["delete_later"].call_args[0][2]

    # ----------------------------------------------------------------
    # /remove
    # ----------------------------------------------------------------
    async def test_remove_user_success(self, admin_mocks):
        self.context.args = ["Queue", "User"]
        admin_mocks["parser"].parse_queue_name.return_value = ("q1", "Queue", ["User"])
        admin_mocks["parser"].parse_remove_args.return_value = (None, "User")

        # Мок возвращает tuple: (removed_name, position)
        admin_mocks["service"].remove_from_queue.return_value = ("User", 1)

        await admin_module.remove_user(self.update, self.context, ctx=self.ctx)

        admin_mocks["service"].remove_from_queue.assert_awaited_once_with(self.ctx, pos=None, user_name="User")
        admin_mocks["service"].update_queue_message.assert_awaited_once()

    async def test_remove_user_not_found_in_queue(self, admin_mocks):
        self.context.args = ["Queue", "Ghost"]
        admin_mocks["parser"].parse_queue_name.return_value = ("q1", "Queue", ["Ghost"])
        admin_mocks["parser"].parse_remove_args.return_value = (None, "Ghost")

        # Мок возвращает (None, None), значит юзер не найден
        admin_mocks["service"].remove_from_queue.return_value = (None, None)

        await admin_module.remove_user(self.update, self.context, ctx=self.ctx)

        admin_mocks["service"].update_queue_message.assert_not_awaited()
        admin_mocks["delete_later"].assert_awaited_once()
        assert "не найден в очереди" in admin_mocks["delete_later"].call_args[0][2]

    # ----------------------------------------------------------------
    # /replace
    # ----------------------------------------------------------------
    async def test_replace_users(self, admin_mocks):
        self.context.args = ["Queue", "u1", "u2"]
        admin_mocks["service"].repo.get_all_queues.return_value = {
            "q1": {"id": "q1", "members": [{"display_name": "u1"}, {"display_name": "u2"}]}
        }
        admin_mocks["parser"].parse_queue_name.return_value = ("q1", "Queue", ["u1", "u2"])
        admin_mocks["parser"].parse_replace_args.return_value = (1, 2, "u1", "u2")

        await admin_module.replace_users(self.update, self.context, ctx=self.ctx)

        admin_mocks["service"].replace_users_queue.assert_awaited_once_with(self.ctx, 1, 2, "u1", "u2")
        admin_mocks["service"].update_queue_message.assert_awaited_once()

    # ----------------------------------------------------------------
    # /rename
    # ----------------------------------------------------------------
    async def test_rename_queue_success(self, admin_mocks):
        self.context.args = ["Old", "New"]
        admin_mocks["service"].repo.get_all_queues.return_value = {"q1": {"name": "Old"}}
        admin_mocks["parser"].parse_queue_name.return_value = ("q1", "Old", ["New"])

        await admin_module.rename_queue(self.update, self.context, ctx=self.ctx)

        admin_mocks["service"].rename_queue.assert_awaited_once_with(self.ctx, "New")
        admin_mocks["service"].update_queue_message.assert_awaited_once()
        assert self.ctx.queue_name == "New"

    async def test_rename_queue_duplicate(self, admin_mocks):
        self.context.args = ["Old", "Existing"]
        admin_mocks["service"].repo.get_all_queues.return_value = {"q1": {"name": "Old"}, "q2": {"name": "Existing"}}
        admin_mocks["parser"].parse_queue_name.return_value = ("q1", "Old", ["Existing"])

        await admin_module.rename_queue(self.update, self.context, ctx=self.ctx)

        admin_mocks["delete_later"].assert_awaited_once()
        assert "уже существует" in admin_mocks["delete_later"].call_args[0][2]
        admin_mocks["service"].rename_queue.assert_not_awaited()

    # ----------------------------------------------------------------
    # /set_expire_time
    # ----------------------------------------------------------------
    async def test_set_expire_time_success(self, admin_mocks):
        self.context.args = ["Queue", "5"]
        admin_mocks["service"].repo.get_queue_by_name.return_value = {"id": "q1", "name": "Queue"}

        await admin_module.set_queue_expiration_time(self.update, self.context, ctx=self.ctx)

        # 5 часов * 3600
        admin_mocks["service"].auto_cleanup_service.reschedule_expiration.assert_awaited_once_with(
            self.context, self.ctx, 18000
        )
        admin_mocks["delete_later"].assert_awaited_once()

    async def test_set_expire_time_invalid_input(self, admin_mocks):
        self.context.args = ["Queue", "abc"]
        await admin_module.set_queue_expiration_time(self.update, self.context, ctx=self.ctx)

        admin_mocks["delete_later"].assert_awaited_once()
        assert "Неверный формат" in admin_mocks["delete_later"].call_args[0][2]

    # ----------------------------------------------------------------
    # /set_description
    # ----------------------------------------------------------------
    async def test_set_description_success(self, admin_mocks):
        self.context.args = ["Queue", "Cool", "Desc"]
        admin_mocks["parser"].parse_queue_name.return_value = ("q1", "Queue", ["Cool", "Desc"])

        self.update.message.text = "/set_description Queue Cool Desc"

        await admin_module.set_queue_description(self.update, self.context, ctx=self.ctx)

        admin_mocks["service"].set_queue_description.assert_awaited_once_with(self.ctx, "Cool Desc")
        admin_mocks["service"].update_queue_message.assert_awaited_once()

    async def test_set_description_reset(self, admin_mocks):
        self.context.args = ["Queue"]  # Нет описания
        admin_mocks["parser"].parse_queue_name.return_value = ("q1", "Queue", [])

        await admin_module.set_queue_description(self.update, self.context, ctx=self.ctx)

        admin_mocks["service"].set_queue_description.assert_awaited_once_with(self.ctx, None)
