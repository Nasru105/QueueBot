from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.queues.models import ActionContext
from app.utils.utils import has_user, is_user_admin, parse_time_str, safe_delete, strip_user_full_name


@pytest.mark.parametrize(
    "user_data, expected",
    [
        ((123, "alice_123", "Alice", "Smith"), "Smith Alice"),
        ((123, "alice_123", "Alice", None), "Alice"),
        ((123, "alice_123", None, "Smith"), "Smith"),
        ((123, "alice_123", None, None), "alice_123"),
        ((123, None, None, None), "123"),
        ((123, None, "Alice", "Smith"), "Smith Alice"),
    ],
)
def test_strip_user_full_name(user_data, expected):
    from telegram import User as TelegramUser

    user = TelegramUser(
        id=user_data[0], is_bot=False, username=user_data[1], first_name=user_data[2], last_name=user_data[3]
    )
    assert strip_user_full_name(user) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "members, user_id, display_name, expected",
    [
        ([{"user_id": 123, "display_name": "Alice"}], 123, "Alice", True),
        ([{"user_id": 123, "display_name": "Alice"}], 456, "Charlie", False),
        ([{"user_id": 123, "display_name": "Alice"}], 456, "Alice", False),
        ([{"display_name": "Bob"}], 456, "Bob", True),
    ],
)
async def test_has_user(members, user_id, display_name, expected):
    assert await has_user(members, user_id, display_name) == expected


@pytest.mark.asyncio
class TestAsyncHelpers:
    """Тесты для асинхронных функций."""

    async def test_safe_delete_success(self):
        mock_bot = MagicMock()
        mock_bot.delete_message = AsyncMock()
        mock_ctx = ActionContext(chat_id=1, chat_title="t", queue_name="q", actor="a")

        await safe_delete(mock_bot, mock_ctx, 101)

        mock_bot.delete_message.assert_awaited_once_with(chat_id=1, message_id=101)

    async def test_safe_delete_failure(self):
        mock_bot = MagicMock()
        mock_bot.delete_message = AsyncMock(side_effect=Exception("Deletion failed"))
        mock_ctx = ActionContext(chat_id=1, chat_title="t", queue_name="q", actor="a")

        # Убеждаемся, что функция не падает, а обрабатывает исключение
        await safe_delete(mock_bot, mock_ctx, 101)
        mock_bot.delete_message.assert_awaited_once()

    @pytest.mark.parametrize(
        "status, expected",
        [
            ("creator", True),
            ("administrator", True),
            ("member", False),
            ("left", False),
        ],
    )
    async def test_is_user_admin(self, status, expected):
        mock_context = MagicMock()
        # Мокаем асинхронный метод get_chat_member
        mock_member = MagicMock()
        mock_member.status = status
        mock_context.bot.get_chat_member = AsyncMock(return_value=mock_member)

        is_admin = await is_user_admin(mock_context, 123, 456)

        assert is_admin == expected
        mock_context.bot.get_chat_member.assert_awaited_once_with(123, 456)

    async def test_is_user_admin_exception(self):
        mock_context = MagicMock()
        mock_context.bot.get_chat_member = AsyncMock(side_effect=Exception("API error"))

        is_admin = await is_user_admin(mock_context, 123, 456)

        assert is_admin is False


def test_parse_time_str():
    dt_obj = datetime(2023, 1, 1, 12, 30, 0)
    dt_str = "01.01.2023 12:30:00"

    assert parse_time_str(dt_obj) == dt_obj
    assert parse_time_str(dt_str) == dt_obj

    with pytest.raises(ValueError):
        parse_time_str("invalid format")
