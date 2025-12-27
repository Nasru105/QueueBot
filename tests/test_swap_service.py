import asyncio

import pytest

from app.queues.services.swap_service.swap_service import SwapNotFound, SwapPermissionError, SwapService


@pytest.mark.asyncio
async def test_create_and_get_swap():
    s = SwapService()
    sid = await s.create_swap(
        chat_id=1,
        queue_id="q1",
        requester_id=2,
        target_id=3,
        requester_name="A",
        target_name="B",
        queue_name="queue",
        ttl=1,
    )
    sw = await s.get_swap(sid)
    assert sw is not None
    assert sw["requester_id"] == 2

    # wait for expiry
    await asyncio.sleep(1.05)
    sw2 = await s.get_swap(sid)
    assert sw2 is None


@pytest.mark.asyncio
async def test_accept_and_decline():
    s = SwapService()
    sid = await s.create_swap(
        chat_id=1,
        queue_id="q2",
        requester_id=10,
        target_id=20,
        requester_name="X",
        target_name="Y",
        queue_name="queue2",
        ttl=10,
    )

    # bad accept (wrong user)
    with pytest.raises(SwapPermissionError):
        await s.accept_swap(sid, by_user_id=999)

    # decline by actual target
    res = await s.decline_swap(sid, by_user_id=20)
    assert res is True

    # after decline swap must be gone
    with pytest.raises(SwapNotFound):
        await s.decline_swap(sid, by_user_id=20)


@pytest.mark.asyncio
async def test_accept_success():
    s = SwapService()
    sid = await s.create_swap(
        chat_id=1,
        queue_id="q3",
        requester_id=11,
        target_id=21,
        requester_name="AA",
        target_name="BB",
        queue_name="queue3",
        ttl=10,
    )
    swapped = await s.accept_swap(sid, by_user_id=21)
    assert swapped["requester_id"] == 11
    # ensure it's deleted
    with pytest.raises(SwapNotFound):
        await s.accept_swap(sid, by_user_id=21)
