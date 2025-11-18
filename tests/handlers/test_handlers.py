from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.handlers import handlers as handlers_mod


class DummyMessage:
    def __init__(self, chat):
        self.chat = chat
        self.message_id = 1
        self.message_thread_id = None


class DummyQuery:
    def __init__(self, data, chat, user):
        self.data = data
        self.from_user = user
        self.message = DummyMessage(chat)
        self.answer = AsyncMock()


@pytest.mark.asyncio
async def test_handle_queue_button_join(monkeypatch):
    chat = SimpleNamespace(id=1, title="TestChat", username=None)
    user = SimpleNamespace(id=5, username="tester")

    repo = SimpleNamespace(
        get_all_queues=AsyncMock(return_value={"Queue 1": {"queue": []}}),
        get_queue=AsyncMock(return_value=[]),
    )
    queue_service = SimpleNamespace(
        repo=repo,
        get_user_display_name=AsyncMock(return_value="Tester"),
        add_to_queue=AsyncMock(),
        remove_from_queue=AsyncMock(),
        update_queue_message=AsyncMock(),
    )
    monkeypatch.setattr(handlers_mod, "queue_service", queue_service)

    query = DummyQuery("queue|0|join", chat, user)
    update = SimpleNamespace(callback_query=query)
    context = MagicMock()

    await handlers_mod.handle_queue_button(update, context)

    queue_service.get_user_display_name.assert_awaited_once()
    queue_service.add_to_queue.assert_awaited_once_with(chat.id, "Queue 1", "Tester", "TestChat")
    queue_service.update_queue_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_queue_button_leave(monkeypatch):
    chat = SimpleNamespace(id=2, title="Chat", username=None)
    user = SimpleNamespace(id=9, username="tester")

    repo = SimpleNamespace(
        get_all_queues=AsyncMock(return_value={"Queue X": {"queue": []}}),
        get_queue=AsyncMock(return_value=["Tester"]),
    )
    queue_service = SimpleNamespace(
        repo=repo,
        get_user_display_name=AsyncMock(return_value="Tester"),
        add_to_queue=AsyncMock(),
        remove_from_queue=AsyncMock(),
        update_queue_message=AsyncMock(),
    )
    monkeypatch.setattr(handlers_mod, "queue_service", queue_service)

    query = DummyQuery("queue|0|leave", chat, user)
    update = SimpleNamespace(callback_query=query)
    context = MagicMock()

    await handlers_mod.handle_queue_button(update, context)

    queue_service.remove_from_queue.assert_awaited_once_with(chat.id, "Queue X", "Tester", "Chat")
    queue_service.update_queue_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_queues_button_get(monkeypatch):
    chat = SimpleNamespace(id=7, title="Chat", username=None)
    user = SimpleNamespace(id=99)

    repo = SimpleNamespace(
        get_all_queues=AsyncMock(return_value={"Queue 1": {}, "Queue 2": {}}),
        get_list_message_id=AsyncMock(return_value=None),
        get_queue_message_id=AsyncMock(return_value=None),
    )
    queue_service = SimpleNamespace(
        repo=repo,
        send_queue_message=AsyncMock(),
    )
    monkeypatch.setattr(handlers_mod, "queue_service", queue_service)

    query = DummyQuery("queues|1|get", chat, user)
    update = SimpleNamespace(callback_query=query)
    context = MagicMock()

    await handlers_mod.handle_queues_button(update, context)

    queue_service.send_queue_message.assert_awaited_once_with(
        chat=chat, thread_id=None, context=context, queue_name="Queue 2"
    )
