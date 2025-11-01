from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.queue_manager import QueueManager


class FakeChat:
    """Фейковый чат для тестов"""

    def __init__(self, chat_id=1, title="TestChat"):
        self.id = chat_id
        self.title = title
        self.username = None


@pytest.fixture
def qm():
    """Создаём новый QueueManager без данных"""
    with patch("app.services.queue_manager.load_data", return_value={}):
        return QueueManager()


@pytest.mark.asyncio
async def test_create_and_get_queue(qm, mocker):
    chat = FakeChat()
    mocker.patch("app.services.queue_manager.save_data")
    mocker.patch("app.services.queue_manager.QueueLogger.log")

    await qm.create_queue(chat, "Очередь 1")

    queues = await qm.get_queues(chat.id)
    assert "Очередь 1" in queues
    assert queues["Очередь 1"]["queue"] == []


@pytest.mark.asyncio
async def test_add_and_remove_user(qm, mocker):
    chat = FakeChat()
    mocker.patch("app.services.queue_manager.save_data")
    mocker.patch("app.services.queue_manager.QueueLogger.joined")
    mocker.patch("app.services.queue_manager.QueueLogger.leaved")

    await qm.create_queue(chat, "Очередь 1")
    await qm.add_to_queue(chat, "Очередь 1", "Иван")

    queue = await qm.get_queue(chat.id, "Очередь 1")
    assert queue == ["Иван"]

    await qm.remove_from_queue(chat, "Очередь 1", "Иван")
    queue = await qm.get_queue(chat.id, "Очередь 1")
    assert queue == []


@pytest.mark.asyncio
async def test_delete_queue(qm, mocker):
    chat = FakeChat()
    mocker.patch("app.services.queue_manager.save_data")
    mocker.patch("app.services.queue_manager.QueueLogger.log")

    await qm.create_queue(chat, "Очередь 1")
    assert "Очередь 1" in await qm.get_queues(chat.id)

    await qm.delete_queue(chat, "Очередь 1")
    queues = await qm.get_queues(chat.id)
    assert "Очередь 1" not in queues


@pytest.mark.asyncio
async def test_rename_queue_existing(qm, mocker):
    chat = FakeChat()
    mocker.patch("app.services.queue_manager.save_data")
    mocker.patch("app.services.queue_manager.QueueLogger.log")

    await qm.create_queue(chat, "Очередь 1")
    await qm.add_to_queue(chat, "Очередь 1", "Иван")

    await qm.rename_queue(chat, "Очередь 1", "Очередь 2")

    queues = await qm.get_queues(chat.id)
    assert "Очередь 2" in queues
    assert queues["Очередь 2"]["queue"] == ["Иван"]


@pytest.mark.asyncio
async def test_rename_queue_not_existing_creates_new(qm, mocker):
    chat = FakeChat()
    mocker.patch("app.services.queue_manager.save_data")
    mocker.patch("app.services.queue_manager.QueueLogger.log")

    await qm.rename_queue(chat, "Неизвестная", "Новая")

    queues = await qm.get_queues(chat.id)
    assert "Новая" in queues
    assert queues["Новая"]["queue"] == []


@pytest.mark.asyncio
async def test_get_queue_text(qm, mocker):
    chat = FakeChat()
    mocker.patch("app.services.queue_manager.save_data")
    await qm.create_queue(chat, "Очередь 1")

    # Пустая очередь
    text = await qm.get_queue_text(chat.id, "Очередь 1")
    assert "Очередь пуста" in text

    # С пользователями
    await qm.add_to_queue(chat, "Очередь 1", "Иван")
    await qm.add_to_queue(chat, "Очередь 1", "Петр")
    text = await qm.get_queue_text(chat.id, "Очередь 1")
    assert "1\\. Иван" in text
    assert "2\\. Петр" in text


@pytest.mark.asyncio
async def test_send_queue_message_creates_message(qm, mocker):
    chat = FakeChat()
    mocker.patch("app.services.queue_manager.save_data")
    mocker.patch("app.services.queue_manager.safe_delete", new_callable=AsyncMock)
    mocker.patch("app.services.queue_manager.queue_keyboard", return_value="keyboard")

    # создаём очередь с пользователями
    await qm.create_queue(chat, "Очередь 1")
    await qm.add_to_queue(chat, "Очередь 1", "Иван")

    # Мокаем bot.send_message
    fake_message = MagicMock()
    fake_message.message_id = 123
    context = MagicMock()
    context.bot.send_message = AsyncMock(return_value=fake_message)

    update = MagicMock()
    update.effective_chat = chat
    update.message = None

    # Вызываем
    await qm.send_queue_message(update, context, "Очередь 1")

    # Проверяем что сообщение было отправлено
    context.bot.send_message.assert_awaited_once()
    args, kwargs = context.bot.send_message.call_args
    assert kwargs["chat_id"] == chat.id
    assert kwargs["parse_mode"] == "MarkdownV2"
    assert kwargs["reply_markup"] == "keyboard"

    # Проверяем, что сохранился last_queue_message_id
    last_id = await qm.get_last_queue_message_id(chat.id, "Очередь 1")
    assert last_id == 123


@pytest.mark.asyncio
async def test_send_queue_message_deletes_previous(qm, mocker):
    chat = FakeChat()
    mocker.patch("services.queue_manager.save_data")
    fake_delete = mocker.patch(
        "services.queue_manager.safe_delete", new_callable=AsyncMock
    )
    mocker.patch("services.queue_manager.queue_keyboard", return_value="keyboard")

    # создаём очередь и сохраняем старый message_id
    await qm.create_queue(chat, "Очередь 1")
    await qm.set_last_queue_message_id(chat.id, "Очередь 1", 99)

    fake_message = MagicMock()
    fake_message.message_id = 123
    context = MagicMock()
    context.bot.send_message = AsyncMock(return_value=fake_message)

    update = MagicMock()
    update.effective_chat = chat
    update.message = None

    await qm.send_queue_message(update, context, "Очередь 1")

    # Проверяем, что safe_delete вызван для старого id
    fake_delete.assert_awaited_once()
    args, kwargs = fake_delete.call_args
    assert args[1].id == chat.id  # второй аргумент — chat
    assert args[2] == 99  # третий аргумент — message_id
