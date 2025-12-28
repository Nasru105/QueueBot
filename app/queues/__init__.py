# queue/__init__.py
from app.queues.service import QueueFacadeService

from .queue_repository import QueueRepository

# Глобальные экземпляры
queue_repo = QueueRepository()
queue_service = QueueFacadeService(repo=queue_repo)
