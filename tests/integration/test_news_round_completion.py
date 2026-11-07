from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from xhs_local.app import LocalApplication
from xhs_local.core.states import WorkTopic
from xhs_local.storage.database import Database
from xhs_local.storage.schema import migrate

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_daily_news_cutoff_keeps_the_final_twenty_minutes() -> None:
    local_midnight = datetime(2026, 8, 31, tzinfo=ZoneInfo("Asia/Shanghai"))

    assert LocalApplication._daily_news_cutoff(local_midnight, 20) == datetime(  # noqa: SLF001
        2026,
        8,
        30,
        15,
        40,
        tzinfo=UTC,
    )


@pytest.mark.parametrize("downtime", [5, 20, 21, None])
def test_restart_resumes_or_catches_up_once_per_platform(tmp_path, monkeypatch, downtime):
    config_root, runtime_root = tmp_path / "config", tmp_path / "runtime"
    shutil.copytree(PROJECT_ROOT / "config", config_root)
    (runtime_root / "sessions").mkdir(parents=True)
    (runtime_root / "sessions/telegram-user.session").write_bytes(b"offline-session-fixture")
    (runtime_root / "secrets").mkdir(parents=True)
    (runtime_root / "secrets/deepseek-api-key").write_text("test-key")
    with Database(runtime_root / "app.sqlite3") as database:
        migrate(database)
    startup = datetime(2026, 9, 13, 8, 0, tzinfo=UTC)
    previous_run = startup - timedelta(minutes=10)
    if downtime is not None:
        (runtime_root / "status.json").write_text(
            json.dumps(
                {
                    "stopped_at": (startup - timedelta(minutes=downtime)).isoformat(),
                    "last_scheduled_run_at": previous_run.isoformat(),
                    "news_daily_cleanup": {"date": "2026-09-13"},
                }
            )
        )

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return startup.astimezone(tz)

    monkeypatch.setattr("xhs_local.app.datetime", Clock)

    async def scenario():
        app = await LocalApplication.create(config_root)
        calls, cooldowns, discarded = [], [], []
        outcomes = {"telegram": "published", "x": "failed", "youtube": "published"}
        short = downtime is not None and downtime <= 20
        assert app.resume_after_restart is short
        if short:
            assert app.scheduled_news_cadence.last_run_at == previous_run
            assert app.daily_news_cleanup_date == "2026-09-13"
        else:
            app.startup_news_ready.set()

        async def pending_count(plugin_id=None, **kwargs):
            return 1

        async def enqueue(**kwargs):
            calls.append(kwargs)
            return outcomes[kwargs["source_plugin"]]

        async def cooldown(interval_minutes=None):
            cooldowns.append(interval_minutes)

        def discard(cutoff, **kwargs):
            assert cutoff == startup
            discarded.append(kwargs["plugin_id"])
            return 2

        app._pending_news_count = pending_count
        app._enqueue_news = enqueue
        app._wait_for_news_publish_cooldown = cooldown
        app.ledger.discard_unpublished_news_before = discard
        task = asyncio.create_task(app._initialize_recent_news())
        try:
            await asyncio.wait_for(app.startup_news_complete.wait(), timeout=1)
            if short:
                assert calls == cooldowns == discarded == []
                assert app.status.snapshot()["news_initialization"]["mode"] == "resume"
            else:
                assert [call["source_plugin"] for call in calls] == ["telegram", "x", "youtube"]
                assert all(
                    call["reason"] == "catchup" and call["wait_for_terminal"] for call in calls
                )
                assert all(call["candidate_window_end"] == startup for call in calls)
                assert cooldowns == [None, None, None]
                assert discarded == ["telegram", "youtube"]  # A failed platform is not purged.
                assert app.status.snapshot()["news_initialization"]["platform_outcomes"] == outcomes
        finally:
            app.stop_event.set()
            await asyncio.wait_for(task, timeout=1)
            app.database.close()

    asyncio.run(scenario())


def test_startup_collection_timeout_cannot_block_formal_scheduling(tmp_path: Path) -> None:
    config_root = tmp_path / "config"
    runtime_root = tmp_path / "runtime"
    shutil.copytree(PROJECT_ROOT / "config", config_root)
    (runtime_root / "sessions").mkdir(parents=True)
    (runtime_root / "sessions/telegram-user.session").write_bytes(b"offline-session-fixture")
    (runtime_root / "secrets").mkdir(parents=True)
    (runtime_root / "secrets/deepseek-api-key").write_text("test-key", encoding="utf-8")
    with Database(runtime_root / "app.sqlite3") as database:
        migrate(database)

    async def scenario() -> None:
        application = await LocalApplication.create(config_root)
        news = application.snapshot.publishing.news.model_copy(
            update={"startup_collection_timeout_seconds": 0.01}
        )
        publishing = application.snapshot.publishing.model_copy(update={"news": news})
        application.snapshot = replace(application.snapshot, publishing=publishing)

        async def pending_count(_plugin_id: str | None = None, **_kwargs) -> int:
            return 0

        application._pending_news_count = pending_count  # type: ignore[method-assign]
        task = asyncio.create_task(application._initialize_recent_news())  # noqa: SLF001
        try:
            await asyncio.wait_for(application.startup_news_complete.wait(), timeout=1)
            assert (
                application.status.snapshot()["news_initialization"]["source_sweep_timed_out"]
                is True
            )
        finally:
            application.stop_event.set()
            await asyncio.wait_for(task, timeout=1)
            application.database.close()

    asyncio.run(scenario())


def test_startup_publication_waits_for_the_global_news_interval(tmp_path: Path) -> None:
    config_root = tmp_path / "config"
    runtime_root = tmp_path / "runtime"
    shutil.copytree(PROJECT_ROOT / "config", config_root)
    (runtime_root / "sessions").mkdir(parents=True)
    (runtime_root / "sessions/telegram-user.session").write_bytes(b"offline-session-fixture")
    (runtime_root / "secrets").mkdir(parents=True)
    (runtime_root / "secrets/deepseek-api-key").write_text("test-key", encoding="utf-8")
    with Database(runtime_root / "app.sqlite3") as database:
        migrate(database)

    async def scenario() -> None:
        application = await LocalApplication.create(config_root)
        news = application.snapshot.publishing.news.model_copy(
            update={"publish_interval_minutes": 0.002}
        )
        publishing = application.snapshot.publishing.model_copy(update={"news": news})
        application.snapshot = replace(application.snapshot, publishing=publishing)
        application.scheduled_news_cadence.wall_now = lambda: datetime(
            2026,
            8,
            28,
            12,
            tzinfo=ZoneInfo("Asia/Shanghai"),
        )
        application.startup_news_ready.set()
        published_at = datetime.now(UTC)
        application.ledger.latest_published_at = lambda **_kwargs: published_at  # type: ignore[method-assign]
        calls: list[float] = []

        async def pending_count(plugin_id: str | None = None, **_kwargs) -> int:
            return 30 if plugin_id in {None, "telegram"} else 0

        async def enqueue_news(**_kwargs) -> None:
            calls.append(asyncio.get_running_loop().time())
            return "not_published"

        application._pending_news_count = pending_count  # type: ignore[method-assign]
        application._enqueue_news = enqueue_news  # type: ignore[method-assign]
        started = asyncio.get_running_loop().time()
        task = asyncio.create_task(application._initialize_recent_news())  # noqa: SLF001
        try:
            await asyncio.wait_for(application.startup_news_complete.wait(), timeout=1)
            assert calls[0] - started >= 0.09
        finally:
            application.stop_event.set()
            await asyncio.wait_for(task, timeout=1)
            application.database.close()

    asyncio.run(scenario())


def test_scheduler_enqueue_waits_until_news_handler_finishes(tmp_path: Path) -> None:
    config_root = tmp_path / "config"
    runtime_root = tmp_path / "runtime"
    shutil.copytree(PROJECT_ROOT / "config", config_root)
    (runtime_root / "sessions").mkdir(parents=True)
    (runtime_root / "sessions/telegram-user.session").write_bytes(b"offline-session-fixture")
    (runtime_root / "secrets").mkdir(parents=True)
    (runtime_root / "secrets/deepseek-api-key").write_text("test-key", encoding="utf-8")
    with Database(runtime_root / "app.sqlite3") as database:
        migrate(database)

    async def scenario() -> None:
        application = await LocalApplication.create(config_root)
        handler_started = asyncio.Event()
        finish_handler = asyncio.Event()

        async def fake_news_service(_work) -> str:
            handler_started.set()
            await finish_handler.wait()
            return "published"

        application.news_service = fake_news_service
        scheduled_before = application.scheduled_news_cadence.last_run_at
        enqueue_task = asyncio.create_task(application._enqueue_news())  # noqa: SLF001
        try:
            async with asyncio.timeout(1):
                while not application.news_round_waiters:
                    await asyncio.sleep(0)
            work_id = next(iter(application.news_round_waiters))
            work = application.work_items.claim(work_id)
            assert work is not None
            handler_task = asyncio.create_task(application._publish_news_work(work))  # noqa: SLF001
            await asyncio.wait_for(handler_started.wait(), timeout=1)
            assert not enqueue_task.done()

            finish_handler.set()
            await asyncio.wait_for(handler_task, timeout=1)
            application.work_items.succeed(work_id)
            await asyncio.wait_for(enqueue_task, timeout=1)
            status = application.status.snapshot()
            assert status["last_news_round_outcome"] == "published"
            assert application.metrics.snapshot()["counters"]["news_notes_published"] == 1
            assert application.scheduled_news_cadence.last_run_at > scheduled_before

            application.remote_operations.unresolved = (  # type: ignore[method-assign]
                lambda **_kwargs: [object()]
            )
            blocked_id = await application._create_work(  # noqa: SLF001
                WorkTopic.NEWS_PUBLISH,
                payload={"source_plugin": "x"},
                wake=False,
            )
            assert blocked_id is not None
            blocked = application.work_items.claim(blocked_id)
            assert blocked is not None
            await application._publish_news_work(blocked)  # noqa: SLF001
            blocked_state = application.work_items.get(blocked_id)
            assert blocked_state.state.value == "WAITING_OPERATOR"
            assert blocked_state.error_class == "REMOTE_CIRCUIT_OPEN"
        finally:
            if not enqueue_task.done():
                enqueue_task.cancel()
                await asyncio.gather(enqueue_task, return_exceptions=True)
            application.database.close()

    asyncio.run(scenario())


def test_application_builds_shared_cadence_for_telegram_x_and_youtube(
    tmp_path: Path,
) -> None:
    config_root = tmp_path / "config"
    runtime_root = tmp_path / "runtime"
    shutil.copytree(PROJECT_ROOT / "config", config_root)
    (runtime_root / "sessions").mkdir(parents=True)
    (runtime_root / "sessions/telegram-user.session").write_bytes(b"offline-session-fixture")
    (runtime_root / "secrets").mkdir(parents=True)
    (runtime_root / "secrets/deepseek-api-key").write_text("test-key", encoding="utf-8")
    with Database(runtime_root / "app.sqlite3") as database:
        migrate(database)

    async def scenario() -> None:
        application = await LocalApplication.create(config_root)
        try:
            assert set(application.news_schedulers) == {"telegram", "x", "youtube"}
            assert len(application.news_schedulers["telegram"].initial_pending) == 13
            expected_x_targets = {
                target.id
                for source in application.snapshot.sources.sources
                if source.plugin == "x" and source.enabled
                for target in source.targets
                if target.enabled
            }
            assert application.news_schedulers["x"].initial_pending == expected_x_targets
            application.news_schedulers["telegram"].local_hour = lambda: 12
            application.news_schedulers["x"].local_hour = lambda: 12
            application.scheduled_news_cadence.wall_now = lambda: datetime(
                2026,
                8,
                31,
                12,
                tzinfo=ZoneInfo("Asia/Shanghai"),
            )
            assert application.news_schedulers["telegram"].interval_seconds() == 20 * 60
            assert application.news_schedulers["x"].interval_seconds() == 20 * 60
            assert application.news_schedulers["telegram"].mode() == "scheduled_only"
            assert application.news_schedulers["x"].mode() == "scheduled_only"
            assert application.news_schedulers["telegram"].batch_size() == 18
            assert application.news_schedulers["x"].batch_size() == 18
            assert application.news_schedulers["telegram"].immediate_five_star_enabled() is False
            assert application.news_schedulers["x"].immediate_five_star_enabled() is False
            assert application.scheduled_news_cadence.interval_seconds() == 20 * 60
            youtube = application.news_schedulers["youtube"]
            youtube.local_hour = lambda: 12
            assert youtube.interval_seconds() == 20 * 60
            assert youtube.mode() == "scheduled_only"
            assert youtube.batch_size() == 18
            assert youtube.immediate_five_star_enabled() is False

            pending = {"telegram": 17, "x": 4, "youtube": 1}
            cadence_calls: list[dict] = []

            async def pending_count(plugin_id: str | None = None) -> int:
                return sum(pending.values()) if plugin_id is None else pending.get(plugin_id, 0)

            async def enqueue_news(**kwargs) -> None:
                cadence_calls.append(kwargs)

            application._pending_news_count = pending_count  # type: ignore[method-assign]
            application._enqueue_news = enqueue_news  # type: ignore[method-assign]
            await application._enqueue_scheduled_news()  # noqa: SLF001
            assert cadence_calls == [{"reason": "scheduled"}]
            cadence_calls.clear()
            pending.update(telegram=0, x=0, youtube=1)
            await application._enqueue_scheduled_news()  # noqa: SLF001
            assert cadence_calls == [{"reason": "scheduled"}]

            cadence_calls.clear()
            pending["telegram"] = 18
            await application._enqueue_scheduled_news()  # noqa: SLF001
            assert cadence_calls == [{"reason": "scheduled"}]
            telegram_work = await application._create_work(  # noqa: SLF001
                WorkTopic.NEWS_PUBLISH,
                payload={"source_plugin": "telegram"},
                wake=False,
            )
            x_work = await application._create_work(  # noqa: SLF001
                WorkTopic.NEWS_PUBLISH,
                payload={"source_plugin": "x"},
                wake=False,
            )
            duplicate_x = await application._create_work(  # noqa: SLF001
                WorkTopic.NEWS_PUBLISH,
                payload={"source_plugin": "x"},
                wake=False,
            )
            assert telegram_work is not None
            assert x_work is None
            assert duplicate_x is None
            claimed_telegram = application.work_items.claim(telegram_work)
            assert claimed_telegram is not None
            assert application.work_items.reconcile_only(
                telegram_work,
                error_summary="historical remote result needs reconciliation",
            )
            replacement_x = await application._create_work(  # noqa: SLF001
                WorkTopic.NEWS_PUBLISH,
                payload={"source_plugin": "x"},
                wake=False,
            )
            assert replacement_x is not None
        finally:
            application.database.close()

    asyncio.run(scenario())
