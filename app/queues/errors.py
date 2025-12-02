class QueueError(Exception):
    """Base class for queue-related errors."""


class ChatNotFoundError(QueueError):
    """Raised when a requested chat does not exist."""


class QueueNotFoundError(QueueError):
    """Raised when a requested queue does not exist."""


class UserNotFoundError(QueueError):
    """Raised when a requested user is not found in a queue or DB."""


class InvalidPositionError(QueueError):
    """Raised when a provided position for insertion/replacement is invalid."""


class QueueAlreadyExistsError(QueueError):
    """Raised when attempting to create a queue that already exists."""


class UserAlreadyExistsError(QueueError):
    """Raised when attempting to add a user that already exists in the queue."""


class MessageServiceError(QueueError):
    """Raised when sending/editing messages fails in the message service."""
