"""
Тесты для UserService.
"""

from unittest.mock import AsyncMock

import pytest
from telegram import User as TelegramUser

from app.queues.user_service import UserService


@pytest.fixture
def mock_repo():
    """Мок репозитория."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def user_service(mock_repo):
    """Фикстура для создания сервиса с моком репозитория."""
    return UserService(mock_repo)


@pytest.fixture
def test_user():
    """Пример пользователя Telegram."""
    return TelegramUser(
        id=123,
        is_bot=False,
        first_name="John",
        last_name="Doe",
    )


@pytest.mark.asyncio
class TestUserServiceGetDisplayName:
    """Тесты получения отображаемого имени."""

    async def test_get_chat_specific_display_name(self, user_service, mock_repo, test_user):
        """Должна вернуть чат-специфичное имя, если оно есть."""
        mock_repo.get_user_display_name = AsyncMock(
            return_value={
                "user_id": 123,
                "display_names": {
                    "100": "John Chat 100",  # для чата 100
                    "200": "John Chat 200",  # для чата 200
                    "global": "John Global",
                },
            }
        )

        result = await user_service.get_user_display_name(test_user, chat_id=100)

        assert result == "John Chat 100"

    async def test_get_global_display_name_when_no_chat_specific(self, user_service, mock_repo, test_user):
        """Должна вернуть глобальное имя если чат-специфичного нет."""
        mock_repo.get_user_display_name = AsyncMock(
            return_value={
                "user_id": 123,
                "display_names": {
                    "global": "John Global",
                },
            }
        )

        result = await user_service.get_user_display_name(test_user, chat_id=100)

        assert result == "John Global"

    async def test_get_full_name_when_no_display_names(self, user_service, mock_repo, test_user):
        """Должна вернуть полное имя если нет сохранённых отображаемых имён."""
        mock_repo.get_user_display_name = AsyncMock(return_value={"user_id": 123, "display_names": {}})

        result = await user_service.get_user_display_name(test_user, chat_id=100)

        assert "John" in result

    async def test_get_display_name_calls_repo(self, user_service, mock_repo, test_user):
        """Должна вызвать репозиторий для получения данных."""
        mock_repo.get_user_display_name = AsyncMock(return_value={"user_id": 123, "display_names": {"global": "John"}})

        await user_service.get_user_display_name(test_user, chat_id=100)

        mock_repo.get_user_display_name.assert_called_once_with(test_user)


@pytest.mark.asyncio
class TestUserServiceSetDisplayName:
    """Тесты установки отображаемого имени."""

    async def test_set_chat_specific_display_name(self, user_service, mock_repo, test_user):
        """Установка чат-специфичного имени."""
        mock_repo.get_user_display_name = AsyncMock(return_value={"user_id": 123, "display_names": {}})
        mock_repo.update_user_display_name = AsyncMock()

        ctx = AsyncMock()
        ctx.chat_id = 100
        await user_service.set_user_display_name(ctx, test_user, "John Custom")

        mock_repo.update_user_display_name.assert_called_once()
        # Проверяем что новое имя добавлено в словарь
        call_args = mock_repo.update_user_display_name.call_args
        display_names = call_args[0][1]
        assert display_names.get("100") == "John Custom"

    async def test_set_global_display_name(self, user_service, mock_repo, test_user):
        """Установка глобального имени."""
        mock_repo.get_user_display_name = AsyncMock(return_value={"user_id": 123, "display_names": {}})
        mock_repo.update_user_display_name = AsyncMock()

        ctx = AsyncMock()
        ctx.chat_id = 100
        await user_service.set_user_display_name(ctx, test_user, "John Global", global_mode=True)

        mock_repo.update_user_display_name.assert_called_once()
        call_args = mock_repo.update_user_display_name.call_args
        display_names = call_args[0][1]
        assert display_names.get("global") == "John Global"

    async def test_set_display_name_overwrites_existing(self, user_service, mock_repo, test_user):
        """Установка нового имени должна перезаписать старое."""
        mock_repo.get_user_display_name = AsyncMock(
            return_value={
                "user_id": 123,
                "display_names": {"100": "Old Name"},
            }
        )
        mock_repo.update_user_display_name = AsyncMock()

        ctx = AsyncMock()
        ctx.chat_id = 100
        await user_service.set_user_display_name(ctx, test_user, "New Name")

        call_args = mock_repo.update_user_display_name.call_args
        display_names = call_args[0][1]
        assert display_names.get("100") == "New Name"


@pytest.mark.asyncio
class TestUserServiceClearDisplayName:
    """Тесты очистки отображаемого имени."""

    async def test_clear_chat_specific_display_name(self, user_service, mock_repo, test_user):
        """Очистка чат-специфичного имени."""
        mock_repo.get_user_display_name = AsyncMock(
            return_value={
                "user_id": 123,
                "display_names": {
                    "100": "John Custom",
                    "global": "John Global",
                },
            }
        )
        mock_repo.update_user_display_name = AsyncMock()

        ctx = AsyncMock()
        ctx.chat_id = 100
        await user_service.clear_user_display_name(ctx, test_user, global_mode=False)

        mock_repo.update_user_display_name.assert_called_once()
        call_args = mock_repo.update_user_display_name.call_args
        display_names = call_args[0][1]
        assert "100" not in display_names

    async def test_clear_global_display_name(self, user_service, mock_repo, test_user):
        """Очистка глобального имени и восстановление стандартного."""
        mock_repo.get_user_display_name = AsyncMock(
            return_value={
                "user_id": 123,
                "display_names": {
                    "global": "John Global",
                },
            }
        )
        mock_repo.update_user_display_name = AsyncMock()

        ctx = AsyncMock()
        ctx.chat_id = 100
        result = await user_service.clear_user_display_name(ctx, test_user, global_mode=True)

        mock_repo.update_user_display_name.assert_called_once()
        # Результат должен быть новым глобальным именем (стандартное)
        assert result is not None

    async def test_clear_nonexistent_display_name(self, user_service, mock_repo, test_user):
        """Очистка несуществующего имени - нужно быть осторожным с доступом к глобальному имени."""
        mock_repo.get_user_display_name = AsyncMock(
            return_value={"user_id": 123, "display_names": {"global": "John Default"}}
        )
        mock_repo.update_user_display_name = AsyncMock()

        ctx = AsyncMock()
        ctx.chat_id = 100
        result = await user_service.clear_user_display_name(ctx, test_user, global_mode=False)

        # После очистки чат-специфичного имени возвращается глобальное имя
        assert result == "John Default"
