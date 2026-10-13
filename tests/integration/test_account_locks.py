from __future__ import annotations

import asyncio

from xhs_local.pipeline.publisher import AccountLocks


def test_same_sink_account_reuses_one_lock_and_serializes_remote_steps() -> None:
    async def scenario() -> None:
        locks = AccountLocks()
        first = locks.get("xiaohongshu", "main")
        assert first is locks.get("xiaohongshu", "main")
        active = 0
        maximum = 0

        async def guarded() -> None:
            nonlocal active, maximum
            async with locks.get("xiaohongshu", "main"):
                active += 1
                maximum = max(maximum, active)
                await asyncio.sleep(0.01)
                active -= 1

        await asyncio.gather(guarded(), guarded(), guarded())
        assert maximum == 1

    asyncio.run(scenario())


def test_different_sink_or_account_has_independent_lock_domain() -> None:
    async def scenario() -> None:
        locks = AccountLocks()
        both_entered = asyncio.Event()
        entered = 0

        async def guarded(sink: str, account: str) -> None:
            nonlocal entered
            async with locks.get(sink, account):
                entered += 1
                if entered == 3:
                    both_entered.set()
                await asyncio.wait_for(both_entered.wait(), timeout=1)

        await asyncio.gather(
            guarded("xiaohongshu", "main"),
            guarded("xiaohongshu", "secondary"),
            guarded("another-sink", "main"),
        )
        assert entered == 3

    asyncio.run(scenario())
