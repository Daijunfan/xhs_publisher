from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from xhs_local.core.contracts import CollectBatch
from xhs_local.core.errors import TransientError
from xhs_local.pipeline.source_scheduler import SourceScheduler
from xhs_local.plugins.contracts import CancellationToken, PluginTarget
from xhs_local.storage.checkpoints import CheckpointRepository
from xhs_local.storage.database import Database
from xhs_local.storage.records import CommitResult
from xhs_local.storage.schema import migrate


def scheduler_fixture(checkpoints, clock, plugin_id, *, fail=False):
    calls = []
    target = PluginTarget("target", "https://example.test/creator", "Fixture", {})
    token = CancellationToken()

    async def collect(request):
        calls.append(request)
        if fail:
            raise TransientError("offline fixture")
        return CollectBatch("source", target.id, (), {})

    async def commit(*_args, **_kwargs):
        return CommitResult((), (), ())

    async def on_batch(*_args):
        if not fail:
            token.cancel()

    scheduler = SourceScheduler(
        SimpleNamespace(app=SimpleNamespace(timezone="UTC"), revision="test"),
        None, checkpoints, SimpleNamespace(commit=commit), on_batch,
    )
    scheduler._status_now = lambda: clock[0]
    scheduler.status[target.id] = {"plugin_id": plugin_id}
    prepared = SimpleNamespace(context=SimpleNamespace(source_id="source"))
    return scheduler, prepared, SimpleNamespace(collect=collect), target, token, calls


async def wait_until(check):
    async with asyncio.timeout(1):
        while not check():
            await asyncio.sleep(0.005)


def test_youtube_restart_uses_persisted_last_poll_before_starting_request(tmp_path, monkeypatch):
    monkeypatch.setattr("xhs_local.pipeline.source_scheduler.SOURCE_CLOCK_RECHECK_SECONDS", 0.01)
    now = datetime.now(UTC)
    clock = [now]
    with Database(tmp_path / "state.sqlite3") as db:
        migrate(db)
        checkpoints = CheckpointRepository(db)
        checkpoints.put("source", "target", {"last_polled_at": now.isoformat()})

        async def run():
            for restart in range(2):
                scheduler, prepared, plugin, target, token, calls = scheduler_fixture(
                    checkpoints, clock, "youtube"
                )
                task = asyncio.create_task(
                    scheduler._target_loop(prepared, plugin, target, 7200, token)
                )
                status = scheduler.status[target.id]
                await wait_until(lambda status=status: "next_run_at" in status)
                assert calls == []
                assert datetime.fromisoformat(scheduler.status[target.id]["next_run_at"]) == (
                    now + timedelta(seconds=7200)
                )
                if restart == 0:
                    token.cancel()
                else:
                    clock[0] = now + timedelta(seconds=7200)
                await asyncio.wait_for(task, 1)
                assert len(calls) == restart

        asyncio.run(run())


@pytest.mark.parametrize("plugin_id,checkpoint", [
    ("youtube", {}), ("telegram", {"last_polled_at": "2099-01-01T00:00:00+00:00"}),
    ("x", {"last_polled_at": "2099-01-01T00:00:00+00:00"}),
])
def test_new_youtube_and_existing_other_sources_keep_immediate_start(plugin_id, checkpoint):
    async def run():
        fixture = scheduler_fixture(
            SimpleNamespace(get=lambda *_args: checkpoint), [datetime.now(UTC)], plugin_id
        )
        scheduler, prepared, plugin, target, token, calls = fixture
        await asyncio.wait_for(scheduler._target_loop(prepared, plugin, target, 7200, token), 1)
        assert len(calls) == 1

    asyncio.run(run())


@pytest.mark.parametrize("plugin_id,minimum,maximum", [
    ("youtube", 7199, 7201), ("telegram", 299, 301), ("x", 299, 301),
])
def test_only_youtube_failure_waits_at_least_its_user_poll_interval(plugin_id, minimum, maximum):
    async def run():
        now = datetime.now(UTC)
        fixture = scheduler_fixture(
            SimpleNamespace(get=lambda *_args: {}), [now], plugin_id, fail=True
        )
        scheduler, prepared, plugin, target, token, calls = fixture
        task = asyncio.create_task(scheduler._target_loop(prepared, plugin, target, 7200, token))
        await wait_until(lambda: "next_run_at" in scheduler.status[target.id])
        deadline = datetime.fromisoformat(scheduler.status[target.id]["next_run_at"])
        delay = (deadline - now).total_seconds()
        assert minimum <= delay <= maximum
        assert len(calls) == 1
        token.cancel()
        await task

    asyncio.run(run())
