from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from xhs_local.pipeline.source_scheduler import (
    NewsPublishScheduler,
    PeriodicNewsCadence,
    _failure_delay,
)


def _settings(
    *,
    threshold: int = 20,
    interval_minutes: float = 15,
    max_news_per_note: int = 7,
    mode: str = "interval",
    batch_size: int = 18,
    immediate_five_star: bool = False,
):
    return SimpleNamespace(
        publish_interval_minutes=interval_minutes,
        source_publish_interval_minutes={"x": 30},
        source_publish_modes={"test": mode},
        source_batch_sizes={"test": batch_size},
        source_immediate_five_star={"test": immediate_five_star},
        night_publish_interval_minutes=45,
        night_start_hour=0,
        night_end_hour=7,
        new_post_threshold=threshold,
        max_news_per_note=max_news_per_note,
    )


async def _until(predicate, timeout: float = 1) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0)


def _daytime_now() -> datetime:
    return datetime.now().astimezone().replace(hour=12)


def test_source_failure_backoff_checks_recovery_within_five_minutes() -> None:
    assert _failure_delay(30, 1) == 60
    assert _failure_delay(30, 4) == 300
    assert _failure_delay(1800, 1) == 300


def test_initial_collection_with_no_pending_posts_does_not_publish() -> None:
    async def scenario() -> None:
        pending = 0
        calls = []

        async def pending_count() -> int:
            return pending

        async def enqueue() -> None:
            calls.append("publish")

        scheduler = NewsPublishScheduler(
            target_ids={"one", "two"},
            settings=_settings,
            enqueue=enqueue,
            pending_count=pending_count,
            local_hour=lambda: 12,
        )
        task = asyncio.create_task(scheduler.run())
        try:
            await scheduler.record_batch("one", 0, initial=True, succeeded=True)
            await scheduler.record_batch("two", 0, initial=True, succeeded=True)
            await asyncio.sleep(0.02)
            assert calls == []
            assert scheduler.accumulated == 0
        finally:
            scheduler.stop()
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_scheduled_only_sources_never_trigger_their_own_publication() -> None:
    async def scenario() -> None:
        calls: list[str] = []

        async def enqueue() -> None:
            calls.append("publish")

        scheduler = NewsPublishScheduler(
            target_ids={"one"},
            settings=lambda: _settings(mode="scheduled_only"),
            enqueue=enqueue,
            pending_count=lambda: asyncio.sleep(0, result=30),
            schedule_key="test",
        )
        task = asyncio.create_task(scheduler.run())
        try:
            await scheduler.record_batch("one", 30, initial=True, succeeded=True)
            await asyncio.sleep(0.02)
            assert calls == []
        finally:
            scheduler.stop()
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_durable_backlog_does_not_wait_for_all_source_targets_to_initialize() -> None:
    async def scenario() -> None:
        pending = 3
        calls = []

        async def enqueue() -> None:
            nonlocal pending
            calls.append("publish")
            pending = 0

        scheduler = NewsPublishScheduler(
            target_ids={"one", "two"},
            settings=lambda: _settings(interval_minutes=0.001),
            enqueue=enqueue,
            pending_count=lambda: asyncio.sleep(0, result=pending),
            local_hour=lambda: 12,
        )
        task = asyncio.create_task(scheduler.run())
        try:
            await _until(lambda: calls == ["publish"])
            assert pending == 0
            assert scheduler.initial_pending == {"one", "two"}
        finally:
            scheduler.stop()
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_twenty_pending_triggers_then_full_cooldown_starts_after_round_completion() -> None:
    async def scenario() -> None:
        pending = 0
        calls: list[float] = []
        first_started = asyncio.Event()
        finish_first = asyncio.Event()
        loop = asyncio.get_running_loop()

        async def pending_count() -> int:
            return pending

        async def enqueue() -> None:
            nonlocal pending
            calls.append(loop.time())
            if len(calls) == 1:
                first_started.set()
                await finish_first.wait()
            pending = max(0, pending - 20)

        settings = _settings(interval_minutes=0.001)
        scheduler = NewsPublishScheduler(
            target_ids={"one"},
            settings=lambda: settings,
            enqueue=enqueue,
            pending_count=pending_count,
            local_hour=lambda: 12,
        )
        task = asyncio.create_task(scheduler.run())
        try:
            await scheduler.record_batch("one", 0, initial=True, succeeded=True)
            pending = 20
            await scheduler.record_batch("one", 20, initial=False, succeeded=True)
            await asyncio.wait_for(first_started.wait(), timeout=1)

            pending = 40
            await scheduler.record_batch("one", 20, initial=False, succeeded=True)
            await asyncio.sleep(0.02)
            assert len(calls) == 1

            round_completed_at = loop.time()
            finish_first.set()
            await asyncio.sleep(0.03)
            assert len(calls) == 1
            await _until(lambda: len(calls) == 2)
            assert calls[1] - round_completed_at >= 0.05
            assert scheduler.accumulated == 0
        finally:
            scheduler.stop()
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_elapsed_interval_publishes_even_one_pending_post() -> None:
    async def scenario() -> None:
        calls = []
        pending = 0

        async def enqueue() -> None:
            nonlocal pending
            calls.append("publish")
            pending = 0

        scheduler = NewsPublishScheduler(
            target_ids={"one"},
            settings=lambda: _settings(interval_minutes=0.0005),
            enqueue=enqueue,
            pending_count=lambda: asyncio.sleep(0, result=pending),
            local_hour=lambda: 12,
        )
        task = asyncio.create_task(scheduler.run())
        try:
            await scheduler.record_batch("one", 0, initial=True, succeeded=True)
            await asyncio.sleep(0.01)
            assert calls == []
            pending = 1
            await scheduler.record_batch("one", 1, initial=False, succeeded=True)
            await _until(lambda: calls == ["publish"] and scheduler.accumulated == 0)
            assert scheduler.accumulated == 0
        finally:
            scheduler.stop()
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_startup_drains_all_pending_posts_before_one_full_cooldown() -> None:
    async def scenario() -> None:
        calls = []
        normal_calls = []
        pending = 14

        async def enqueue() -> None:
            nonlocal pending
            calls.append("publish")
            pending = max(0, pending - 7)

        scheduler = NewsPublishScheduler(
            target_ids={"one"},
            settings=lambda: _settings(interval_minutes=0.001),
            enqueue=lambda: asyncio.sleep(0, result=normal_calls.append("publish")),
            startup_enqueue=enqueue,
            pending_count=lambda: asyncio.sleep(0, result=pending),
            local_hour=lambda: 12,
        )
        task = asyncio.create_task(scheduler.run())
        try:
            await scheduler.record_batch("one", 0, initial=True, succeeded=True)
            await _until(lambda: calls == ["publish", "publish"])
            assert normal_calls == []
            assert pending == 0
            await _until(lambda: scheduler.cooldown_until is not None)
            assert scheduler.cooldown_until is not None
        finally:
            scheduler.stop()
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_startup_stops_draining_when_a_round_makes_no_progress() -> None:
    async def scenario() -> None:
        calls = []
        pending = 5

        async def enqueue() -> None:
            calls.append("publish")

        scheduler = NewsPublishScheduler(
            target_ids={"one"},
            settings=lambda: _settings(interval_minutes=0.001),
            enqueue=enqueue,
            pending_count=lambda: asyncio.sleep(0, result=pending),
            local_hour=lambda: 12,
        )
        task = asyncio.create_task(scheduler.run())
        try:
            await scheduler.record_batch("one", 0, initial=True, succeeded=True)
            await _until(lambda: calls == ["publish"])
            await _until(lambda: scheduler.cooldown_until is not None)
            assert pending == 5
        finally:
            scheduler.stop()
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_capacity_mode_holds_seventeen_and_publishes_once_at_eighteen() -> None:
    async def scenario() -> None:
        pending = 17
        calls = []

        async def publish_capacity() -> None:
            nonlocal pending
            calls.append("capacity")
            pending = 0

        scheduler = NewsPublishScheduler(
            target_ids={"one"},
            settings=lambda: _settings(mode="capacity", max_news_per_note=18),
            enqueue=lambda: asyncio.sleep(0),
            capacity_enqueue=publish_capacity,
            pending_count=lambda: asyncio.sleep(0, result=pending),
            local_hour=lambda: 12,
            schedule_key="test",
        )
        task = asyncio.create_task(scheduler.run())
        try:
            await scheduler.record_batch("one", 0, initial=True, succeeded=True)
            await asyncio.sleep(0.03)
            assert calls == []
            pending = 18
            await scheduler.record_batch("one", 1, initial=False, succeeded=True)
            await _until(lambda: calls == ["capacity"] and scheduler.accumulated == 0)
            assert scheduler.cooldown_until is None
            assert scheduler.next_check_at is None
        finally:
            scheduler.stop()
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_capacity_no_progress_waits_until_next_configured_cycle() -> None:
    async def scenario() -> None:
        pending = 18
        calls = 0

        async def publish_capacity() -> None:
            nonlocal calls, pending
            calls += 1
            if calls == 2:
                pending = 0

        scheduler = NewsPublishScheduler(
            target_ids={"one"},
            settings=lambda: _settings(
                mode="capacity",
                batch_size=18,
                interval_minutes=0.001,
            ),
            enqueue=lambda: asyncio.sleep(0),
            capacity_enqueue=publish_capacity,
            pending_count=lambda: asyncio.sleep(0, result=pending),
            local_hour=lambda: 12,
            schedule_key="test",
        )
        task = asyncio.create_task(scheduler.run())
        try:
            await _until(lambda: calls == 2 and scheduler.accumulated == 0)
            assert scheduler.cooldown_until is None
        finally:
            scheduler.stop()
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_five_star_check_can_single_publish_before_capacity_batch() -> None:
    async def scenario() -> None:
        pending = 0
        priority_calls = []
        capacity_calls = []

        async def check_five_star() -> None:
            nonlocal pending
            priority_calls.append(pending)
            if pending == 1:
                pending = 0

        async def publish_capacity() -> None:
            nonlocal pending
            capacity_calls.append(pending)
            pending = 0

        scheduler = NewsPublishScheduler(
            target_ids={"one"},
            settings=lambda: _settings(
                mode="capacity",
                max_news_per_note=18,
                immediate_five_star=True,
            ),
            enqueue=lambda: asyncio.sleep(0),
            capacity_enqueue=publish_capacity,
            five_star_enqueue=check_five_star,
            pending_count=lambda: asyncio.sleep(0, result=pending),
            schedule_key="test",
        )
        task = asyncio.create_task(scheduler.run())
        try:
            await scheduler.record_batch("one", 0, initial=True, succeeded=True)
            pending = 1
            await scheduler.record_batch("one", 1, initial=False, succeeded=True)
            await _until(lambda: priority_calls == [1] and pending == 0)
            assert capacity_calls == []

            pending = 18
            await scheduler.record_batch("one", 18, initial=False, succeeded=True)
            await _until(lambda: len(priority_calls) == 2 and capacity_calls == [18])
        finally:
            scheduler.stop()
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_all_immediate_five_star_candidates_are_drained_one_per_round() -> None:
    async def scenario() -> None:
        pending = 3
        calls: list[int] = []

        async def check_five_star() -> None:
            nonlocal pending
            calls.append(pending)
            if pending > 1:
                pending -= 1

        scheduler = NewsPublishScheduler(
            target_ids={"one"},
            settings=lambda: _settings(
                mode="capacity",
                batch_size=18,
                immediate_five_star=True,
            ),
            enqueue=lambda: asyncio.sleep(0),
            five_star_enqueue=check_five_star,
            pending_count=lambda: asyncio.sleep(0, result=pending),
            schedule_key="test",
        )
        task = asyncio.create_task(scheduler.run())
        try:
            await scheduler.record_batch("one", 0, initial=True, succeeded=True)
            await _until(lambda: calls == [3, 2, 1])
            assert pending == 1
        finally:
            scheduler.stop()
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_night_still_triggers_at_twenty_but_uses_longer_post_round_cooldown() -> None:
    scheduler = NewsPublishScheduler(
        target_ids=set(),
        settings=_settings,
        enqueue=lambda: asyncio.sleep(0),
        local_hour=lambda: 2,
    )

    asyncio.run(scheduler.record_batch("one", 20, initial=False, succeeded=True))

    assert scheduler.interval_seconds() == 45 * 60
    assert scheduler.accumulated == 20
    assert scheduler.trigger.is_set()


def test_cooldown_uses_wall_deadline_across_mac_sleep() -> None:
    timezone = ZoneInfo("Asia/Shanghai")
    moments = iter(
        [
            datetime(2026, 8, 25, 4, 30, tzinfo=timezone),
            datetime(2026, 8, 25, 8, 35, tzinfo=timezone),
        ]
    )
    scheduler = NewsPublishScheduler(
        target_ids=set(),
        settings=_settings,
        enqueue=lambda: asyncio.sleep(0),
        local_hour=lambda: 4,
        wall_now=lambda: next(moments),
    )

    asyncio.run(scheduler._cooldown())  # noqa: SLF001

    assert scheduler.cooldown_until is None


def test_elapsed_wall_deadline_does_not_wait_again_after_wake() -> None:
    timezone = ZoneInfo("Asia/Shanghai")
    now = datetime(2026, 8, 25, 8, 35, tzinfo=timezone)
    scheduler = NewsPublishScheduler(
        target_ids=set(),
        settings=_settings,
        enqueue=lambda: asyncio.sleep(0),
        wall_now=lambda: now,
    )

    expired = datetime(2026, 8, 25, 5, 15, tzinfo=timezone)
    triggered = asyncio.run(  # noqa: F841
        scheduler._wait_for_interval(  # noqa: SLF001
            scheduler.trigger,
            expired - timedelta(minutes=45),
            status_field="next_check_at",
        )
    )

    assert triggered is False


def test_wait_recomputes_interval_when_night_changes_to_day(monkeypatch) -> None:
    monkeypatch.setattr("xhs_local.pipeline.source_scheduler.WALL_CLOCK_RECHECK_SECONDS", 0.001)
    timezone = ZoneInfo("Asia/Shanghai")
    started = datetime(2026, 8, 26, 6, 48, tzinfo=timezone)
    clock = [started]
    scheduler = NewsPublishScheduler(
        target_ids=set(),
        settings=_settings,
        enqueue=lambda: asyncio.sleep(0),
        local_hour=lambda: clock[0].hour,
        wall_now=lambda: clock[0],
    )

    async def scenario() -> bool:
        task = asyncio.create_task(
            scheduler._wait_for_interval(  # noqa: SLF001
                scheduler.trigger,
                started,
                status_field="next_check_at",
            )
        )
        await asyncio.sleep(0.003)
        assert scheduler.next_check_at == datetime(2026, 8, 26, 7, 33, tzinfo=timezone).isoformat()
        clock[0] = datetime(2026, 8, 26, 7, 4, tzinfo=timezone)
        return await asyncio.wait_for(task, timeout=1)

    assert asyncio.run(scenario()) is False
    assert scheduler.next_check_at == datetime(2026, 8, 26, 7, 3, tzinfo=timezone).isoformat()


def test_cross_midnight_night_window_boundaries() -> None:
    settings = _settings()
    settings.night_start_hour = 22
    settings.night_end_hour = 7
    at_23 = NewsPublishScheduler(
        target_ids=set(),
        settings=lambda: settings,
        enqueue=lambda: asyncio.sleep(0),
        local_hour=lambda: 23,
    )
    at_12 = NewsPublishScheduler(
        target_ids=set(),
        settings=lambda: settings,
        enqueue=lambda: asyncio.sleep(0),
        local_hour=lambda: 12,
    )

    assert at_23.interval_seconds() == 45 * 60
    assert at_12.interval_seconds() == 15 * 60


def test_source_specific_daytime_interval_does_not_change_night_cooldown() -> None:
    daytime = NewsPublishScheduler(
        target_ids=set(),
        settings=_settings,
        enqueue=lambda: asyncio.sleep(0),
        local_hour=lambda: 12,
        schedule_key="x",
    )
    night = NewsPublishScheduler(
        target_ids=set(),
        settings=_settings,
        enqueue=lambda: asyncio.sleep(0),
        local_hour=lambda: 2,
        schedule_key="x",
    )

    assert daytime.interval_seconds() == 30 * 60
    assert night.interval_seconds() == 45 * 60


def test_periodic_news_cadence_reads_runtime_config_dynamically() -> None:
    settings = _settings(interval_minutes=15)
    cadence = PeriodicNewsCadence(
        settings=lambda: settings,
        enqueue=lambda: asyncio.sleep(0),
        ready=lambda: asyncio.sleep(0),
        wall_now=_daytime_now,
    )

    assert cadence.interval_seconds() == 15 * 60
    settings.publish_interval_minutes = 5
    assert cadence.interval_seconds() == 5 * 60


def test_periodic_news_cadence_uses_the_night_interval_before_eight() -> None:
    settings = _settings(interval_minutes=20)
    settings.night_publish_interval_minutes = 30
    settings.night_end_hour = 8
    night = PeriodicNewsCadence(
        settings=lambda: settings,
        enqueue=lambda: asyncio.sleep(0),
        ready=lambda: asyncio.sleep(0),
        wall_now=lambda: datetime(2026, 8, 31, 7, 59, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    day = PeriodicNewsCadence(
        settings=lambda: settings,
        enqueue=lambda: asyncio.sleep(0),
        ready=lambda: asyncio.sleep(0),
        wall_now=lambda: datetime(2026, 8, 31, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert night.interval_seconds() == 30 * 60
    assert day.interval_seconds() == 20 * 60


def test_periodic_deadline_resets_after_any_confirmed_news_publication() -> None:
    async def scenario() -> None:
        calls: list[str] = []
        settings = _settings(interval_minutes=0.002)

        async def enqueue() -> None:
            calls.append("scheduled")

        cadence = PeriodicNewsCadence(
            settings=lambda: settings,
            enqueue=enqueue,
            ready=lambda: asyncio.sleep(0),
            wall_now=_daytime_now,
        )
        task = asyncio.create_task(cadence.run())
        try:
            await asyncio.sleep(0.03)
            cadence.note_published()
            await asyncio.sleep(0.07)
            assert calls == []
            await _until(lambda: calls == ["scheduled"])
        finally:
            cadence.stop()
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_periodic_deadline_starts_before_startup_initialization_finishes() -> None:
    async def scenario() -> None:
        calls: list[str] = []
        settings = _settings(interval_minutes=0.001)

        async def ready() -> None:
            await asyncio.sleep(0.08)

        async def enqueue() -> None:
            calls.append("scheduled")

        cadence = PeriodicNewsCadence(
            settings=lambda: settings,
            enqueue=enqueue,
            ready=ready,
            wall_now=_daytime_now,
        )
        task = asyncio.create_task(cadence.run())
        try:
            await _until(lambda: calls == ["scheduled"])
        finally:
            cadence.stop()
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())
