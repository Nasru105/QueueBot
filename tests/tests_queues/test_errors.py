"""
Тесты для ошибок приложения.
"""

import pytest

from app.queues.errors import (
    ChatNotFoundError,
    InvalidPositionError,
    MessageServiceError,
    QueueAlreadyExistsError,
    QueueError,
    QueueNotFoundError,
    UserAlreadyExistsError,
    UserNotFoundError,
)


class TestQueueErrorHierarchy:
    """Тесты для иерархии ошибок."""

    def test_all_errors_inherit_from_queue_error(self):
        """Все специфичные ошибки должны наследоваться от QueueError."""
        errors = [
            ChatNotFoundError,
            QueueNotFoundError,
            UserNotFoundError,
            InvalidPositionError,
            QueueAlreadyExistsError,
            UserAlreadyExistsError,
            MessageServiceError,
        ]
        for error_class in errors:
            assert issubclass(error_class, QueueError)

    def test_queue_error_inheritance_from_exception(self):
        """QueueError должна наследоваться от Exception."""
        assert issubclass(QueueError, Exception)

    def test_can_raise_and_catch_queue_error(self):
        """Должна быть возможность бросать и ловить QueueError."""
        with pytest.raises(QueueError):
            raise QueueError("Test error")

    def test_can_catch_specific_error_as_queue_error(self):
        """Должна быть возможность ловить специфичную ошибку как QueueError."""
        with pytest.raises(QueueError):
            raise UserNotFoundError("User not found")

    def test_error_messages_preserved(self):
        """Сообщения об ошибках должны сохраняться."""
        msg = "User John not found"
        error = UserNotFoundError(msg)
        assert str(error) == msg

    def test_chat_not_found_error(self):
        """Тест ошибки ChatNotFoundError."""
        with pytest.raises(ChatNotFoundError):
            raise ChatNotFoundError("Chat 123 not found")

    def test_queue_not_found_error(self):
        """Тест ошибки QueueNotFoundError."""
        with pytest.raises(QueueNotFoundError):
            raise QueueNotFoundError("Queue abc123 not found")

    def test_invalid_position_error(self):
        """Тест ошибки InvalidPositionError."""
        with pytest.raises(InvalidPositionError):
            raise InvalidPositionError("Position 10 is out of range")

    def test_queue_already_exists_error(self):
        """Тест ошибки QueueAlreadyExistsError."""
        with pytest.raises(QueueAlreadyExistsError):
            raise QueueAlreadyExistsError("Queue already exists")

    def test_user_already_exists_error(self):
        """Тест ошибки UserAlreadyExistsError."""
        with pytest.raises(UserAlreadyExistsError):
            raise UserAlreadyExistsError("User already in queue")

    def test_message_service_error(self):
        """Тест ошибки MessageServiceError."""
        with pytest.raises(MessageServiceError):
            raise MessageServiceError("Failed to send message")
