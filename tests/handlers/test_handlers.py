from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.handlers.handlers import handle_queue_button, handle_queues_button


class DummyMessage:
    def __init__(self, chat):
        self.chat = chat
        self.message_id = 1
        self.message_thread_id = None


class DummyQuery:
    def __init__(self, data, chat, from_user):
        self.data = data
        self.from_user = from_user
        self.message = DummyMessage(chat)
        self.answer = AsyncMock()


@pytest.mark.asyncio
async def test_handle_queue_button_join(monkeypatch):
    chat = SimpleNamespace(id=1, title="TestChat")
    user = SimpleNamespace(username="nouser", first_name="Ivan", last_name=None)

    # Fake queue manager
    fake_qm = SimpleNamespace()
    fake_qm.get_queues = AsyncMock(return_value={"Очередь 1": {}})
    fake_qm.get_queue = AsyncMock(return_value=[])
    fake_qm.add_to_queue = AsyncMock()
    fake_qm.remove_from_queue = AsyncMock()
    fake_qm.update_queue_message = AsyncMock()

    monkeypatch.setattr("app.handlers.handlers.queue_manager", fake_qm)

    query = DummyQuery("queue|0|join", chat, user)
    update = SimpleNamespace(callback_query=query)
    context = MagicMock()

    await handle_queue_button(update, context)

    fake_qm.add_to_queue.assert_awaited_once()
    fake_qm.update_queue_message.assert_awaited_once_with(
        chat, query, "Очередь 1", context
    )


@pytest.mark.asyncio
async def test_handle_queue_button_leave(monkeypatch):
    chat = SimpleNamespace(id=1, title="TestChat")
    user = SimpleNamespace(username="nouser", first_name="Ivan", last_name=None)

    fake_qm = SimpleNamespace()
    fake_qm.get_queues = AsyncMock(return_value={"Очередь 1": {}})
    fake_qm.get_queue = AsyncMock(return_value=["Ivan"])
    fake_qm.add_to_queue = AsyncMock()
    fake_qm.remove_from_queue = AsyncMock()
    fake_qm.update_queue_message = AsyncMock()

    monkeypatch.setattr("app.handlers.handlers.queue_manager", fake_qm)

    query = DummyQuery("queue|0|leave", chat, user)
    update = SimpleNamespace(callback_query=query)
    context = MagicMock()

    await handle_queue_button(update, context)

    fake_qm.remove_from_queue.assert_awaited_once()
    fake_qm.update_queue_message.assert_awaited_once_with(
        chat, query, "Очередь 1", context
    )


@pytest.mark.asyncio
async def test_handle_queues_button_get(monkeypatch):
    chat = SimpleNamespace(id=1, title="TestChat")

    fake_qm = SimpleNamespace()
    fake_qm.get_last_queue_message_id = AsyncMock(return_value=None)
    fake_qm.get_queues = AsyncMock(return_value={"Очередь 1": {}})
    fake_qm.get_queue = AsyncMock(return_value=[])
    fake_qm.get_queue_text = AsyncMock(return_value="текст очереди")
    fake_qm.set_last_queue_message_id = AsyncMock()

    monkeypatch.setattr("app.handlers.handlers.queue_manager", fake_qm)

    # monkeypatch update_existing_queues_info to avoid side-effects
    monkeypatch.setattr(
        "app.handlers.handlers.update_existing_queues_info", AsyncMock()
    )

    # prepare context bot
    fake_message = MagicMock()
    fake_message.message_id = 123
    context = MagicMock()
    context.bot.send_message = AsyncMock(return_value=fake_message)
    context.bot.get_chat_member = AsyncMock(
        return_value=SimpleNamespace(status="creator")
    )

    query = DummyQuery("queues|0|get", chat, SimpleNamespace(id=2))
    update = SimpleNamespace(callback_query=query)

    await handle_queues_button(update, context)

    context.bot.send_message.assert_awaited_once()
    fake_qm.set_last_queue_message_id.assert_awaited_once_with(
        chat.id, "Очередь 1", 123
    )
