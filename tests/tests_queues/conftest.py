from unittest.mock import AsyncMock, MagicMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.queues.models import ActionContext
from app.queues.service import QueueFacadeService
from app.queues.services.auto_cleanup_service import QueueAutoCleanupService
from app.services.logger import QueueLogger


@pytest.fixture
def action_context():
    """Стандартный ActionContext для тестов"""
    return ActionContext(chat_id=123, queue_id="q1", queue_name="TestQueue")


@pytest.fixture(scope="module")
def mock_bot():
    mock_bot = AsyncMock()
    return mock_bot


@pytest.fixture
def mock_repo():
    """Мок репозитория."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_scheduler():
    """Мок для AsyncIOScheduler"""
    scheduler = MagicMock(spec=AsyncIOScheduler)
    scheduler.add_job = MagicMock()
    scheduler.remove_job = MagicMock()
    scheduler.get_job = MagicMock()
    return scheduler


@pytest.fixture
def mock_logger():
    """Мок логгера."""
    logger = AsyncMock(spec=QueueLogger)
    return logger


@pytest.fixture
def auto_cleanup_service(mock_bot, mock_repo, mock_scheduler, mock_logger):
    """Фикстура для создания экземпляра сервиса с моками"""
    return QueueAutoCleanupService(bot=mock_bot, repo=mock_repo, scheduler=mock_scheduler, logger=mock_logger)


@pytest.fixture
def facade_service(mock_bot, mock_repo, mock_logger, mock_scheduler):
    """Фикстура для создания фасада сервиса с моками."""
    service = QueueFacadeService(mock_bot, mock_repo, mock_logger, mock_scheduler)
    return service
