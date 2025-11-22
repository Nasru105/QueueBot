from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import BadRequest

from app.queue_service.queue_service import QueueService

queue_service_module = import_module("app.queue_service.queue_service")


@pytest.mark.asyncio
async def test_get_queue_text_formats_entries(monkeypatch):
    repo = SimpleNamespace(get_queue=AsyncMock(return_value=["Alice", "Bob"]))
    service = QueueService(repo)

    text = await service.get_queue_text(chat_id=1, queue_name="Очередь 1")

    assert "*`Очередь 1`*" in text
    assert "1\\. Alice" in text
    assert "2\\. Bob" in text


@pytest.mark.asyncio
async def test_generate_queue_name_skips_existing():
    repo = SimpleNamespace(
        get_queue=AsyncMock(side_effect=[[1], [1], []]),
    )
    service = QueueService(repo)

    name = await service.generate_queue_name(chat_id=1)

    assert name == "Очередь 3"
    assert repo.get_queue.await_count == 3


@pytest.mark.asyncio
async def test_get_user_display_name_priority(monkeypatch):
    repo = SimpleNamespace(
        get_user_display_name=AsyncMock(
            return_value={
                "display_names": {"global": "Global", "123": "Local"},
            }
        )
    )
    service = QueueService(repo)

    user = {"id": 1, "username": "tester"}
    name = await service.get_user_display_name(user, chat_id=123)
    assert name == "Local"


@pytest.mark.asyncio
async def test_set_user_display_name_updates_repo(monkeypatch):
    user_doc = {"display_names": {"global": "Global"}}
    repo = SimpleNamespace(
        get_user_display_name=AsyncMock(return_value=user_doc),
        update_user_display_name=AsyncMock(),
    )
    service = QueueService(repo)

    user = SimpleNamespace(id=7, username="tester", last_name="", first_name="Tester")

    await service.set_user_display_name(user, "Chat Tester", chat_id=321, chat_title="Chat")

    repo.update_user_display_name.assert_awaited_once_with(7, {"global": "Global", "321": "Chat Tester"})


@pytest.fixture
def service_with_repo(monkeypatch):
    repo = SimpleNamespace(
        set_queue_message_id=AsyncMock(),
        get_queue_message_id=AsyncMock(return_value=999),
        get_all_queues=AsyncMock(),
    )
    service = QueueService(repo)
    monkeypatch.setattr(service, "get_queue_text", AsyncMock(return_value="rendered"))
    monkeypatch.setattr(service, "get_queue_index", AsyncMock(return_value=0))
    monkeypatch.setattr(queue_service_module, "queue_keyboard", lambda idx: f"keyboard-{idx}")
    return service, repo


@pytest.mark.asyncio
async def test_update_queue_message_edits_via_query(service_with_repo):
    service, repo = service_with_repo
    query = SimpleNamespace(
        edit_message_text=AsyncMock(),
        message=SimpleNamespace(message_id=777),
    )

    await service.update_queue_message(chat_id=1, queue_name="Q1", query_or_update=query)

    query.edit_message_text.assert_awaited_once_with(
        text="rendered", parse_mode="MarkdownV2", reply_markup="keyboard-0"
    )
    repo.set_queue_message_id.assert_awaited_once_with(1, "Q1", 777)


@pytest.mark.asyncio
async def test_update_queue_message_edits_via_context(service_with_repo):
    service, repo = service_with_repo
    repo.get_queue_message_id = AsyncMock(return_value=333)
    service.repo = repo

    context = SimpleNamespace(bot=SimpleNamespace(edit_message_text=AsyncMock()))
    update = SimpleNamespace()

    await service.update_queue_message(chat_id=5, queue_name="Q", query_or_update=update, context=context)

    context.bot.edit_message_text.assert_awaited_once_with(
        chat_id=5, message_id=333, text="rendered", parse_mode="MarkdownV2", reply_markup="keyboard-0"
    )
    service.repo.set_queue_message_id.assert_awaited_once_with(5, "Q", 333)


@pytest.mark.asyncio
async def test_update_queue_message_ignores_not_modified(service_with_repo):
    service, repo = service_with_repo
    query = SimpleNamespace(
        edit_message_text=AsyncMock(side_effect=BadRequest("Message is not modified")),
        message=SimpleNamespace(message_id=111),
    )

    await service.update_queue_message(chat_id=1, queue_name="Q", query_or_update=query)

    repo.set_queue_message_id.assert_not_called()


@pytest.mark.asyncio
async def test_clear_user_display_name_global(monkeypatch):
    repo = SimpleNamespace(
        get_user_display_name=AsyncMock(return_value={"display_names": {"global": "Old"}}),
        update_user_display_name=AsyncMock(),
    )
    service = QueueService(repo)
    user = SimpleNamespace(id=9, username=None, last_name="Last", first_name="First")

    await service.clear_user_display_name(user, chat_id=None, chat_title="Chat")

    repo.update_user_display_name.assert_awaited_once_with(9, {"global": "Last First"})


@pytest.mark.asyncio
async def test_clear_user_display_name_chat_specific(monkeypatch):
    repo = SimpleNamespace(
        get_user_display_name=AsyncMock(return_value={"display_names": {"123": "Custom", "global": "Base"}}),
        update_user_display_name=AsyncMock(),
    )
    service = QueueService(repo)
    user = SimpleNamespace(id=10, username="user", last_name="", first_name="Name")

    await service.clear_user_display_name(user, chat_id=123, chat_title="Chat")

    repo.update_user_display_name.assert_awaited_once_with(10, {"global": "Base"})


@pytest.mark.asyncio
async def test_update_existing_queues_info_updates_only_known_messages(monkeypatch):
    repo = SimpleNamespace(
        get_all_queues=AsyncMock(
            return_value={
                "Q1": {"queue": ["u1"], "last_queue_message_id": 5},
                "Q2": {"queue": [], "last_queue_message_id": None},
            }
        )
    )
    service = QueueService(repo)
    monkeypatch.setattr(service, "get_queue_text", AsyncMock(return_value="rendered"))
    monkeypatch.setattr(queue_service_module, "queue_keyboard", lambda idx: f"keyboard-{idx}")

    bot = SimpleNamespace(edit_message_text=AsyncMock())
    chat = SimpleNamespace(id=42)

    await service.update_existing_queues_info(bot, chat, chat_title="Chat")

    bot.edit_message_text.assert_awaited_once_with(
        chat_id=42,
        message_id=5,
        text="rendered",
        parse_mode="MarkdownV2",
        reply_markup="keyboard-0",
    )


@pytest.mark.asyncio
async def test_update_existing_queues_info_ignores_not_modified(monkeypatch):
    repo = SimpleNamespace(
        get_all_queues=AsyncMock(
            return_value={
                "Q1": {"queue": [], "last_queue_message_id": 5},
            }
        )
    )
    service = QueueService(repo)
    monkeypatch.setattr(service, "get_queue_text", AsyncMock(return_value="rendered"))
    monkeypatch.setattr(
        queue_service_module,
        "queue_keyboard",
        lambda idx: f"keyboard-{idx}",
    )

    bot = SimpleNamespace(edit_message_text=AsyncMock(side_effect=BadRequest("Message is not modified")))
    chat = SimpleNamespace(id=7)

    await service.update_existing_queues_info(bot, chat, chat_title="Chat")

    bot.edit_message_text.assert_awaited_once()
