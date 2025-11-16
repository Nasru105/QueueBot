# queue/__init__.py
from .queue_repository import QueueRepository
from .queue_service import QueueService

# Глобальные экземпляры
queue_repo = QueueRepository()
queue_service = QueueService(queue_repo)

__all__ = ["queue_service"]
