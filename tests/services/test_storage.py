from types import SimpleNamespace

import pytest

from app.queue_service import queue_repository as repo_module
from app.queue_service.queue_repository import QueueRepository


class FakeResult:
    def __init__(self, deleted_count=0, modified_count=0):
        self.deleted_count = deleted_count
        self.modified_count = modified_count


class FakeCollection:
    def __init__(self, key_field):
        self.storage = {}
        self.key_field = key_field

    def _key(self, query):
        return query.get(self.key_field)

    async def find_one(self, query, projection=None):
        key = self._key(query)
        doc = self.storage.get(key)
        if not doc:
            return None
        if projection:
            return {k: doc.get(k) for k in projection.keys() if k in doc}
        return doc.copy()

    async def insert_one(self, doc):
        key = doc[self.key_field]
        self.storage[key] = doc.copy()
        return FakeResult()

    async def update_one(self, query, update, upsert=False):
        key = self._key(query)
        doc = self.storage.get(key)
        if not doc:
            if not upsert:
                return FakeResult()
            doc = {self.key_field: key}
        if "$set" in update:
            doc.update(update["$set"])
        self.storage[key] = doc
        return FakeResult(modified_count=1)

    async def delete_one(self, query):
        key = self._key(query)
        existed = self.storage.pop(key, None)
        return FakeResult(deleted_count=1 if existed else 0)


@pytest.fixture
def repo(monkeypatch):
    queue_col = FakeCollection("chat_id")
    user_col = FakeCollection("user_id")
    monkeypatch.setattr(repo_module, "queue_collection", queue_col)
    monkeypatch.setattr(repo_module, "user_collection", user_col)
    return QueueRepository()


@pytest.mark.asyncio
async def test_create_queue_and_add_user(repo):
    await repo.create_queue(chat_id=1, chat_title="Chat", queue_name="Q1")
    await repo.add_to_queue(1, "Q1", "Alice")
    queue = await repo.get_queue(1, "Q1")
    assert queue == ["Alice"]


@pytest.mark.asyncio
async def test_delete_queue_removes_document(repo):
    await repo.create_queue(1, "Chat", "Q1")
    deleted = await repo.delete_queue(1, "Q1")
    assert deleted is True
    assert await repo.get_chat(1) is None


@pytest.mark.asyncio
async def test_set_and_get_queue_message_id(repo):
    await repo.create_queue(1, "Chat", "Q1")
    await repo.set_queue_message_id(1, "Q1", 555)
    msg_id = await repo.get_queue_message_id(1, "Q1")
    assert msg_id == 555


@pytest.mark.asyncio
async def test_get_all_queues_returns_dict(repo):
    await repo.create_queue(1, "Chat", "Q1")
    await repo.add_to_queue(1, "Q1", "A")
    queues = await repo.get_all_queues(1)
    assert "Q1" in queues
    assert queues["Q1"]["queue"] == ["A"]


@pytest.mark.asyncio
async def test_add_to_queue_skips_duplicates(repo):
    await repo.create_queue(1, "Chat", "Q1")
    first = await repo.add_to_queue(1, "Q1", "Alice")
    second = await repo.add_to_queue(1, "Q1", "Alice")

    assert first == 1
    assert second is None
    assert await repo.get_queue(1, "Q1") == ["Alice"]


@pytest.mark.asyncio
async def test_remove_from_queue_returns_position(repo):
    await repo.create_queue(1, "Chat", "Q1")
    await repo.update_queue(1, "Q1", ["Alice", "Bob"])

    position = await repo.remove_from_queue(1, "Q1", "Bob")

    assert position == 2
    assert await repo.get_queue(1, "Q1") == ["Alice"]


@pytest.mark.asyncio
async def test_update_queue_overwrites_entries(repo):
    await repo.create_queue(1, "Chat", "Q1")
    await repo.update_queue(1, "Q1", ["X", "Y"])

    assert await repo.get_queue(1, "Q1") == ["X", "Y"]


@pytest.mark.asyncio
async def test_rename_queue_updates_existing(repo):
    await repo.create_queue(1, "Chat", "Q1")
    await repo.rename_queue(1, "Q1", "Q2")

    queues = await repo.get_all_queues(1)
    assert "Q2" in queues
    assert "Q1" not in queues


@pytest.mark.asyncio
async def test_rename_queue_creates_when_missing(repo):
    await repo.create_queue(1, "Chat", "Q1")
    await repo.rename_queue(1, "Unknown", "Q2")

    queues = await repo.get_all_queues(1)
    assert {"Q1", "Q2"} == set(queues.keys())


@pytest.mark.asyncio
async def test_list_message_id_helpers(repo):
    await repo.create_queue(1, "Chat", "Q1")
    await repo.set_list_message_id(1, 900)
    assert await repo.get_list_message_id(1) == 900
    await repo.clear_list_message_id(1)
    assert await repo.get_list_message_id(1) is None


@pytest.mark.asyncio
async def test_get_user_display_name_creates_document(repo):
    user = SimpleNamespace(id=5, username="tester", last_name="Doe", first_name="John")

    doc = await repo.get_user_display_name(user)

    assert doc["display_names"]["global"] == "Doe John"
    stored = repo_module.user_collection.storage[5]
    assert stored["username"] == "tester"


@pytest.mark.asyncio
async def test_get_user_display_name_updates_username(repo):
    repo_module.user_collection.storage[5] = {
        "user_id": 5,
        "username": "old",
        "display_names": {"global": "Old"},
    }
    user = SimpleNamespace(id=5, username="new", last_name=None, first_name=None)

    await repo.get_user_display_name(user)

    assert repo_module.user_collection.storage[5]["username"] == "new"


@pytest.mark.asyncio
async def test_update_user_display_name(repo):
    await repo.get_user_display_name(SimpleNamespace(id=7, username="u", last_name=None, first_name=None))

    await repo.update_user_display_name(7, {"global": "Custom"})

    assert repo_module.user_collection.storage[7]["display_names"] == {"global": "Custom"}
