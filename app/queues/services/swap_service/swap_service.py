from asyncio import create_task, sleep
from typing import Optional
from uuid import uuid4

from app.queues.errors import QueueError


class SwapNotFound(QueueError):
    pass


class SwapPermissionError(QueueError):
    pass


class SwapService:
    def __init__(self):
        # in-memory store: swap_id -> dict
        self._swaps: dict[str, dict] = {}

    async def create_swap(
        self,
        chat_id: int,
        queue_id: str,
        requester_id: int,
        target_id: int,
        requester_name: Optional[str] = None,
        target_name: Optional[str] = None,
        queue_name: Optional[str] = None,
        ttl: int = 120,
    ) -> str:
        swap_id = uuid4().hex
        self._swaps[swap_id] = {
            "chat_id": chat_id,
            "queue_id": queue_id,
            "requester_id": requester_id,
            "target_id": target_id,
            "requester_name": requester_name,
            "target_name": target_name,
            "queue_name": queue_name,
        }

        # schedule expiry
        create_task(self._expire_swap(swap_id, ttl))
        return swap_id

    async def _expire_swap(self, swap_id: str, delay: int):
        await sleep(delay)
        self._swaps.pop(swap_id, None)

    async def get_swap(self, swap_id: str) -> Optional[dict]:
        return self._swaps.get(swap_id)

    async def delete_swap(self, swap_id: str):
        self._swaps.pop(swap_id, None)

    async def accept_swap(self, swap_id: str, by_user_id: int) -> dict:
        swap = self._swaps.get(swap_id)
        if not swap:
            raise SwapNotFound()
        if int(by_user_id) != int(swap.get("target_id")):
            raise SwapPermissionError()
        # remove and return swap payload for controller to process
        self._swaps.pop(swap_id, None)
        return swap

    async def decline_swap(self, swap_id: str, by_user_id: int) -> bool:
        swap = self._swaps.get(swap_id)
        if not swap:
            raise SwapNotFound()
        if int(by_user_id) != int(swap.get("target_id")):
            raise SwapPermissionError()
        self._swaps.pop(swap_id, None)
        return True


# singleton instance for simple DI
swap_service = SwapService()
