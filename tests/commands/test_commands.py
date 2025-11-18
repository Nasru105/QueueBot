from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.commands import queue as queue_cmd


@pytest.mark.asyncio
async def test_create_uses_explicit_name(monkeypatch):
    chat = SimpleNamespace(id=42, title="ChatTitle", username=None)
    message = SimpleNamespace(message_id=10, message_thread_id=None)
    update = SimpleNamespace(effective_chat=chat, message=message)
    context = SimpleNamespace(args=["My", "Queue"])

    safe_delete = AsyncMock()
    monkeypatch.setattr(queue_cmd, "safe_delete", safe_delete)

    queue_service = SimpleNamespace(
        repo=SimpleNamespace(get_queue_message_id=AsyncMock(return_value=None)),
        create_queue=AsyncMock(),
        send_queue_message=AsyncMock(),
        generate_queue_name=AsyncMock(),
    )
    monkeypatch.setattr(queue_cmd, "queue_service", queue_service)

    await queue_cmd.create(update, context)

    safe_delete.assert_awaited_once_with(context, chat, message.message_id)
    queue_service.repo.get_queue_message_id.assert_awaited_once_with(chat.id, "My Queue")
    queue_service.create_queue.assert_awaited_once_with(chat.id, "My Queue", "ChatTitle")
    queue_service.send_queue_message.assert_awaited_once_with(chat, None, context, "My Queue")


@pytest.mark.asyncio
async def test_queues_sends_keyboard_and_tracks_message(monkeypatch):
    chat = SimpleNamespace(id=1, title="ChatTitle", username=None)
    message = SimpleNamespace(message_id=99, message_thread_id=None)
    update = SimpleNamespace(effective_chat=chat, message=message)

    safe_delete = AsyncMock()
    monkeypatch.setattr(queue_cmd, "safe_delete", safe_delete)

    keyboard = MagicMock()
    monkeypatch.setattr(queue_cmd, "queues_keyboard", AsyncMock(return_value=keyboard))

    repo = SimpleNamespace(
        get_list_message_id=AsyncMock(return_value=777),
        get_all_queues=AsyncMock(return_value={"Q1": {}, "Q2": {}}),
        set_list_message_id=AsyncMock(),
        clear_list_message_id=AsyncMock(),
    )

    queue_service = SimpleNamespace(repo=repo)
    monkeypatch.setattr(queue_cmd, "queue_service", queue_service)

    sent_message = SimpleNamespace(message_id=123)
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock(return_value=sent_message)))
    context.args = []

    await queue_cmd.queues(update, context)

    # Команда удаляется и удаляется предыдущее меню
    assert safe_delete.await_count == 2
    safe_delete.assert_any_await(context, chat, message.message_id)
    safe_delete.assert_any_await(context, chat, 777)

    repo.get_list_message_id.assert_awaited_once_with(chat.id)
    repo.set_list_message_id.assert_awaited_once_with(chat.id, 123)
    context.bot.send_message.assert_awaited_once()
    _, kwargs = context.bot.send_message.call_args
    assert kwargs["reply_markup"] is keyboard
