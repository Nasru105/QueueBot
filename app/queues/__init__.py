# queue/__init__.py
from app.queues.service import QueueFacadeService
from app.queues.inline_keyboards import queue_keyboard

from .queue_repository import QueueRepository

# Глобальные экземпляры
queue_repo = QueueRepository()
queue_service = QueueFacadeService(repo=queue_repo, keyboard_factory=queue_keyboard)
