from asyncio import Lock

_chat_locks: dict[int, Lock] = {}


def get_chat_lock(chat_id: int) -> Lock:
    """Return a Lock object per chat_id (in-memory implementation).

    This abstraction allows replacing with a distributed lock implementation later.
    """
    if chat_id not in _chat_locks:
        _chat_locks[chat_id] = Lock()
    return _chat_locks[chat_id]
