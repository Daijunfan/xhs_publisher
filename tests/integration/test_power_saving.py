from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from xhs_local import app as app_module
from xhs_local.app import LocalApplication
from xhs_local.configuration.loader import load_snapshot
from xhs_local.core.states import WorkTopic
from xhs_local.pipeline.source_scheduler import (
    SOURCE_CLOCK_RECHECK_SECONDS,
    WALL_CLOCK_RECHECK_SECONDS,
)
from xhs_local.storage.database import Database
from xhs_local.storage.schema import migrate

PROJECT_ROOT = Path(__file__).resolve().parents[2]


async def make_app(tmp_path):
    config, runtime = tmp_path / "config", tmp_path / "runtime"
    shutil.copytree(PROJECT_ROOT / "config", config)
    for name in ("sessions", "secrets"):
        (runtime / name).mkdir(parents=True)
    (runtime / "sessions/telegram-user.session").write_bytes(b"offline-fixture")
    (runtime / "secrets/deepseek-api-key").write_text("test-key")
    with Database(runtime / "app.sqlite3") as database:
        migrate(database)
    return await LocalApplication.create(config)


def test_low_power_polling_keeps_sources_and_publication_rules_enabled():
    snapshot = load_snapshot(PROJECT_ROOT / "config")
    sources = {source.plugin: source for source in snapshot.sources.sources}
    assert {key: source.poll_seconds for key, source in sources.items()} == {
        "telegram": 300,
        "x": 3600,
        "youtube": 7200,
    }
    assert all(source.enabled for source in sources.values())
    assert sources["x"].options["max_posts_per_target"] == 20
    news = snapshot.publishing.news
    assert news.publish_interval_minutes == 20
    assert news.night_publish_interval_minutes == 30
    assert news.max_news_per_note == 18
    assert news.restart_resume_minutes == 20
    assert SOURCE_CLOCK_RECHECK_SECONDS == 300
    assert WALL_CLOCK_RECHECK_SECONDS == 30  # Publication timers are unchanged.


def test_status_never_recursively_scans_directories(tmp_path, monkeypatch):
    async def run():
        app = await make_app(tmp_path)
        try:

            def forbidden_scan(*args, **kwargs):
                raise AssertionError("status must not traverse file directories")

            monkeypatch.setattr(Path, "rglob", forbidden_scan)
            app.work_items.create(WorkTopic.RECORD_COLLECTED)
            snapshot = app._status_snapshot()
            assert snapshot["work_states"]["READY"] == 1
            assert "runtime_bytes" not in snapshot
            assert WorkTopic.RESOURCE_PUBLISH not in app.queues
            assert not hasattr(app, "resource_service")
            assert not (app.snapshot.runtime_root / "inbox/documents").exists()
        finally:
            app.database.close()

    asyncio.run(run())


def test_slower_housekeeping_still_stops_immediately(tmp_path):
    async def run():
        app = await make_app(tmp_path)
        tasks = [asyncio.create_task(app._config_watch()), asyncio.create_task(app._status_loop())]
        try:
            await asyncio.sleep(0)
            app.stop_event.set()
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=0.5)
            assert app_module.CONFIG_WATCH_SECONDS == 5
            assert app_module.STATUS_REFRESH_SECONDS == 30
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            app.database.close()

    asyncio.run(run())
