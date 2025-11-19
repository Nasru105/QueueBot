import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import BadRequest

import app.utils.utils as utils


def test_parse_queue_args_prefers_longest_match():
    args = ["Очередь", "1", "по", "физике", "дальше"]
    queues = ["Очередь 1", "Очередь 1 по физике", "Очередь 2"]

    queue_name, rest = utils.parse_queue_args(args, queues)

    assert queue_name == "Очередь 1 по физике"
    assert rest == ["дальше"]


def test_parse_queue_args_returns_none_when_no_match():
    queue_name, rest = utils.parse_queue_args(["Неизвестная"], ["Очередь 1"])

    assert queue_name is None
    assert rest == []


def test_parse_users_names_finds_two_distinct_entries():
    queue = ["Alice", "Bob", "Charlie"]

    name1, name2 = utils.parse_users_names(["Alice", "Bob"], queue)

    assert (name1, name2) == ("Alice", "Bob")


def test_parse_users_names_returns_none_when_not_found():
    name1, name2 = utils.parse_users_names(["Unknown", "Name"], ["Alice"])

    assert name1 is None
    assert name2 is None


def test_get_user_name_prefers_first_and_last_name():
    user = SimpleNamespace(username=None, first_name="  Иван ", last_name=" Петров ", id=5)

    assert utils.strip_user_full_name(user) == "Петров Иван"


def test_get_user_name_falls_back_to_username():
    user = SimpleNamespace(username="nickname", first_name=" ", last_name=None, id=7)

    assert utils.strip_user_full_name(user) == "nickname"


def test_get_user_name_falls_back_to_id():
    user = SimpleNamespace(username=None, first_name=" ", last_name=None, id=99)

    assert utils.strip_user_full_name(user) == "99"


@pytest.mark.asyncio
async def test_delete_later_waits_and_calls_safe_delete(monkeypatch):
    sleep_calls = []
    safe_calls = []

    async def fake_sleep(value):
        sleep_calls.append(value)

    async def fake_safe(context, chat, message_id):
        safe_calls.append((context, chat, message_id))

    monkeypatch.setattr(utils.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(utils, "safe_delete", fake_safe)

    context = object()
    chat = SimpleNamespace(id=42)

    await utils.delete_later(context, chat, 777, time=0.1)

    assert sleep_calls == [0.1]
    assert safe_calls == [(context, chat, 777)]


@pytest.mark.asyncio
async def test_safe_delete_calls_bot_delete_message():
    bot = AsyncMock()
    context = SimpleNamespace(bot=bot)
    chat = SimpleNamespace(id=1, title="Chat", username=None)

    await utils.safe_delete(context, chat, 55)

    bot.delete_message.assert_awaited_once_with(chat_id=1, message_id=55)


@pytest.mark.asyncio
async def test_safe_delete_ignores_missing_message():
    bot = AsyncMock()
    bot.delete_message.side_effect = BadRequest(message="Message to delete not found")
    context = SimpleNamespace(bot=bot)
    chat = SimpleNamespace(id=1, title="Chat", username=None)

    # Should not raise
    await utils.safe_delete(context, chat, 66)

    bot.delete_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_safe_delete_reraises_unexpected_badrequest():
    bot = AsyncMock()
    bot.delete_message.side_effect = BadRequest(message="Forbidden")
    context = SimpleNamespace(bot=bot)
    chat = SimpleNamespace(id=1, title="Chat", username=None)

    with pytest.raises(BadRequest):
        await utils.safe_delete(context, chat, 77)


@pytest.mark.asyncio
async def test_safe_delete_logs_other_exceptions(monkeypatch):
    bot = AsyncMock()
    bot.delete_message.side_effect = RuntimeError("boom")
    context = SimpleNamespace(bot=bot)
    chat = SimpleNamespace(id=1, title="Chat name", username="chat")

    logs = []

    def fake_log(cls, chat_title="Unknown Chat", queue_name="Unknown queue", action="action", level=logging.INFO):
        logs.append((chat_title, queue_name, action, level))

    monkeypatch.setattr(utils.QueueLogger, "log", classmethod(fake_log))

    await utils.safe_delete(context, chat, 88)

    assert logs and logs[0][0] == "Chat name"
    assert "Не удалось удалить сообщение 88" in logs[0][2]
