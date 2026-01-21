# queue/__init__.py
from app.queues.service import QueueFacadeService
from app.services.mongo_storage import mongo_db

from .queue_repository import QueueRepository

# Глобальные экземпляры
queue_repo = QueueRepository(mongo_db.db)
queue_service = QueueFacadeService(repo=queue_repo)
