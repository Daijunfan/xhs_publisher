from __future__ import annotations

import asyncio
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from xhs_local.app import LocalApplication
from xhs_local.core.errors import TransientError
from xhs_local.core.states import WorkState, WorkTopic
from xhs_local.storage.database import Database
from xhs_local.storage.schema import migrate


async def make_app(tmp_path):
    config = tmp_path / "config"
    runtime = tmp_path / "runtime"
    shutil.copytree(Path(__file__).resolve().parents[2] / "config", config)
    for name in ("sessions", "secrets"):
        (runtime / name).mkdir(parents=True)
    (runtime / "sessions/telegram-user.session").write_bytes(b"offline-fixture")
    (runtime / "secrets/deepseek-api-key").write_text("test-key")
    with Database(runtime / "app.sqlite3") as db:
        migrate(db)
    return await LocalApplication.create(config)


def test_short_outage_keeps_candidates_and_resets_cadence_on_success(tmp_path):
    async def run():
        app = await make_app(tmp_path)
        try:
            work_id = app.work_items.create(WorkTopic.NEWS_PUBLISH, payload={"reason": "scheduled"})
            work = app.work_items.claim(work_id)

            async def offline(_work):
                raise TransientError("simulated train tunnel")

            app.news_service = offline
            with pytest.raises(TransientError):
                await app._publish_news_work(work)
            since = app.news_outage_since
            assert app.checkpoints.get("news_recovery", "state")["since"] == since.isoformat()
            app.scheduled_news_cadence.last_run_at = datetime.now(UTC) - timedelta(hours=2)

            async def online(_work):
                return "published"

            app.news_service = online
            await app._publish_news_work(work)
            assert app.news_outage_since is None
            assert app.news_recovery_cutoff is None
            assert app.checkpoints.get("news_recovery", "state") is None
            assert datetime.now(UTC) - app.scheduled_news_cadence.last_run_at < timedelta(seconds=1)
        finally:
            app.database.close()

    asyncio.run(run())


def test_long_outage_hands_off_to_the_same_single_platform_catchup_without_double_publish(tmp_path):
    async def run():
        app = await make_app(tmp_path)
        try:
            work_id = app.work_items.create(WorkTopic.NEWS_PUBLISH, payload={"reason": "scheduled"})
            work = app.work_items.claim(work_id)
            app.news_outage_since = datetime.now(UTC) - timedelta(minutes=21)

            async def must_not_publish(_work):
                pytest.fail("old scheduled work must not publish before catch-up")

            app.news_service = must_not_publish
            await app._publish_news_work(work)
            cutoff = app.news_recovery_cutoff
            assert cutoff is not None
            assert app.work_items.get(work_id).state is WorkState.SUCCEEDED
            assert app.checkpoints.get("news_recovery", "state")["cutoff"] == cutoff.isoformat()
            calls, retired = [], []

            async def enqueue(**kwargs):
                calls.append(kwargs)
                return "published"

            async def pending(*args, **kwargs):
                return 1

            async def cooldown(*args):
                return None

            app._enqueue_news = enqueue
            app._pending_news_count = pending
            app._wait_for_news_publish_cooldown = cooldown
            app.ledger.discard_unpublished_news_before = lambda *args, **kw: (
                retired.append(kw["plugin_id"]) or 0
            )
            # Regular cadence is held while the recovery pass owns publication.
            await app._enqueue_scheduled_news()
            assert calls == []
            await app._catch_up_news(cutoff)
            assert [call["source_plugin"] for call in calls] == ["telegram", "x", "youtube"]
            assert all(
                call["reason"] == "catchup" and call["candidate_window_end"] == cutoff
                for call in calls
            )
            assert retired == ["telegram", "x", "youtube"]
            await app._clear_news_recovery()
            assert app.news_recovery_cutoff is None
        finally:
            app.database.close()

    asyncio.run(run())


def test_recovery_checkpoint_survives_restart(tmp_path):
    async def run():
        app = await make_app(tmp_path)
        app.news_outage_since = datetime.now(UTC) - timedelta(hours=2)
        app.news_recovery_cutoff = datetime.now(UTC)
        await app._save_news_recovery()
        expected = app.news_recovery_cutoff
        config = app.snapshot.config_root
        app.database.close()
        restarted = await LocalApplication.create(config)
        try:
            assert restarted.news_recovery_cutoff == expected
            assert restarted.news_outage_since is not None
        finally:
            restarted.database.close()

    asyncio.run(run())


def test_startup_catchup_persists_its_window_before_waiting_for_network(tmp_path):
    async def run():
        app = await make_app(tmp_path)
        task = asyncio.create_task(app._initialize_recent_news())
        try:
            async with asyncio.timeout(1):
                while app.checkpoints.get("news_recovery", "state") is None:
                    await asyncio.sleep(0.01)
            assert (
                app.checkpoints.get("news_recovery", "state")["cutoff"]
                == app.startup_at.isoformat()
            )
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            app.database.close()

    asyncio.run(run())


def test_stuck_source_is_cancelled_without_committing_its_checkpoint(monkeypatch):
    from xhs_local.pipeline.source_scheduler import SourceScheduler
    from xhs_local.plugins.contracts import CancellationToken, PluginTarget

    async def run():
        monkeypatch.setattr("xhs_local.pipeline.source_scheduler.COLLECTION_TIMEOUT_SECONDS", 0.01)
        snapshot = SimpleNamespace(app=SimpleNamespace(timezone="Asia/Shanghai"), revision="test")
        checkpoints = SimpleNamespace(get=lambda *args: {})
        cancelled = []

        async def collect(request):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)

        async def committed(*args, **kwargs):
            pytest.fail("timed out source must not advance its checkpoint")

        async def batch(*args):
            scheduler.stopping = True

        scheduler = SourceScheduler(
            snapshot, None, checkpoints, SimpleNamespace(commit=committed), batch
        )
        target = PluginTarget("source", "source", "source", {})
        scheduler.status[target.id] = {}
        prepared = SimpleNamespace(context=SimpleNamespace(source_id="source"))
        await asyncio.wait_for(
            scheduler._target_loop(
                prepared, SimpleNamespace(collect=collect), target, 1800, CancellationToken()
            ),
            1,
        )
        assert cancelled == [True]
        assert scheduler.status[target.id]["failures"] == 1

    asyncio.run(run())
