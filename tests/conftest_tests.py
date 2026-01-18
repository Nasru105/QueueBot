"""
Конфигурация pytest для асинхронных тестов.
Расширяет базовую конфигурацию из конфтеста проекта.
"""

import asyncio

import pytest


@pytest.fixture
def event_loop():
    """Создание event loop для асинхронных тестов."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_action_context():
    """Mock ActionContext для тестов."""
    from app.queues.models import ActionContext

    return ActionContext(
        chat_id=123,
        chat_title="Test Chat",
        queue_id="test_queue",
        queue_name="Test Queue",
        actor="test_user",
    )
