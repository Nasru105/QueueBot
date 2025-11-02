from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.commands.queue import create, queues


@pytest.mark.asyncio
async def test_create_calls_queue_manager(monkeypatch):
    chat = SimpleNamespace(id=1, title="Chat")

    fake_qm = SimpleNamespace()
    fake_qm.create_queue = AsyncMock()
    fake_qm.send_queue_message = AsyncMock()

    monkeypatch.setattr("app.commands.queue.queue_manager", fake_qm)

    update = SimpleNamespace(
        effective_chat=chat,
        message=SimpleNamespace(message_id=10, message_thread_id=None),
    )
    context = MagicMock()
    context.args = ["Очередь", "1"]

    await create(update, context)

    fake_qm.create_queue.assert_awaited_once_with(chat, "Очередь 1")
    fake_qm.send_queue_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_queues_no_active(monkeypatch):
    chat = SimpleNamespace(id=1, title="Chat")

    fake_qm = SimpleNamespace()
    fake_qm.get_queues = AsyncMock(return_value={})
    fake_qm.get_last_queues_message_id = AsyncMock(return_value=None)
    fake_qm.set_last_queues_message_id = AsyncMock()

    monkeypatch.setattr("app.commands.queue.queue_manager", fake_qm)

    update = SimpleNamespace(
        effective_chat=chat,
        message=SimpleNamespace(message_id=10, message_thread_id=None),
    )
    context = MagicMock()
    context.bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=77))

    await queues(update, context)

    context.bot.send_message.assert_awaited()
    fake_qm.set_last_queues_message_id.assert_awaited_once_with(chat.id, None)
