from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import yaml

from xhs_local.app import LocalApplication
from xhs_local.observability.status import read_status
from xhs_local.storage.database import Database
from xhs_local.storage.schema import migrate

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _prepare_runtime(tmp_path: Path) -> tuple[Path, Path]:
    config_root = tmp_path / "config"
    runtime_root = tmp_path / "runtime"
    shutil.copytree(PROJECT_ROOT / "config", config_root)
    (runtime_root / "sessions").mkdir(parents=True)
    (runtime_root / "sessions/telegram-user.session").write_bytes(b"offline-session-fixture")
    (runtime_root / "secrets").mkdir(parents=True)
    (runtime_root / "secrets/deepseek-api-key").write_text("test-key", encoding="utf-8")
    with Database(runtime_root / "app.sqlite3") as database:
        migrate(database)
    return config_root, runtime_root


def test_application_falls_back_to_last_active_revision_when_files_are_invalid(
    tmp_path: Path,
) -> None:
    config_root, _runtime_root = _prepare_runtime(tmp_path)

    async def scenario() -> None:
        first = await LocalApplication.create(config_root)
        active_revision = first.snapshot.revision
        first.database.close()
        (config_root / "publishing.yaml").write_text("version: [", encoding="utf-8")

        restarted = await LocalApplication.create(config_root)
        try:
            assert restarted.snapshot.revision == active_revision
            assert restarted.status.snapshot()["degraded"] is True
        finally:
            restarted.database.close()

    asyncio.run(scenario())


def test_disabled_sources_and_sinks_run_as_one_healthy_idle_application(tmp_path: Path) -> None:
    config_root, runtime_root = _prepare_runtime(tmp_path)
    sources_path = config_root / "sources.yaml"
    sources = yaml.safe_load(sources_path.read_text(encoding="utf-8"))
    for source in sources["sources"]:
        source["enabled"] = False
    sources_path.write_text(
        yaml.safe_dump(sources, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    publishing_path = config_root / "publishing.yaml"
    publishing = yaml.safe_load(publishing_path.read_text(encoding="utf-8"))
    for route in publishing["routes"]:
        route["enabled"] = False
    for sink in publishing["sinks"].values():
        sink["enabled"] = False
    publishing_path.write_text(
        yaml.safe_dump(publishing, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    app_path = config_root / "app.yaml"
    app_config = yaml.safe_load(app_path.read_text(encoding="utf-8"))
    app_config["status"]["port"] = 27654
    app_path.write_text(
        yaml.safe_dump(app_config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    async def scenario() -> None:
        application = await LocalApplication.create(config_root)
        application._start_caffeinate = lambda: None  # noqa: SLF001

        async def stop_soon() -> None:
            await asyncio.sleep(0.05)
            application.request_stop()

        await asyncio.gather(application.run(), stop_soon())

    asyncio.run(scenario())
    state = read_status(runtime_root / "status.json")
    assert state is not None
    assert state["ready"] is False
    assert state["source_targets"] == {}
