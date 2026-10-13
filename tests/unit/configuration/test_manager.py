from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest
import yaml

from xhs_local.configuration.history import ConfigHistory
from xhs_local.configuration.loader import ConfigurationError
from xhs_local.configuration.manager import ConfigManager
from xhs_local.storage.database import Database
from xhs_local.storage.schema import migrate

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _setup(tmp_path: Path):
    config_root = tmp_path / "config"
    shutil.copytree(PROJECT_ROOT / "config", config_root)
    database = Database(tmp_path / "runtime/app.sqlite3")
    migrate(database)
    history = ConfigHistory(database, tmp_path / "runtime/config-history", config_root)
    reports = []

    async def preflight(snapshot):
        reports.append(snapshot.revision)
        return {"ok": True, "revision": snapshot.revision}

    manager = ConfigManager(config_root, history, preflight, debounce_seconds=0)
    return config_root, database, history, manager, reports


def _change_publish_interval(config_root: Path, value: int) -> None:
    path = config_root / "publishing.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["news"]["publish_interval_minutes"] = value
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _swap_review_models(config_root: Path) -> None:
    path = config_root / "publishing.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["news"]["first_review_model"] = "deepseek-v4-flash"
    data["news"]["second_review_model"] = "deepseek-v4-pro"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_valid_candidate_is_applied_then_atomically_marked_active(tmp_path: Path) -> None:
    config_root, database, history, manager, reports = _setup(tmp_path)
    applied = []

    async def scenario() -> None:
        initial, degraded = await manager.load_initial()
        assert degraded is False
        _change_publish_interval(config_root, 16)

        async def apply(previous, candidate):
            assert manager.current is previous
            assert history.last_active().revision == previous.revision
            applied.append((previous.revision, candidate.revision))

        changed = await manager.refresh(apply)
        assert changed is not None
        assert manager.current is changed
        assert history.last_active().revision == changed.revision

    try:
        asyncio.run(scenario())
        assert len(applied) == 1
        assert len(reports) == 2
        assert {row["status"] for row in history.revisions()} == {"ACTIVE", "SUPERSEDED"}
    finally:
        database.close()


def test_review_model_swap_is_applied_as_one_runtime_revision(tmp_path: Path) -> None:
    config_root, database, history, manager, _reports = _setup(tmp_path)
    applied = []

    async def scenario() -> None:
        initial, _ = await manager.load_initial()
        _swap_review_models(config_root)

        async def apply(previous, candidate):
            assert previous is initial
            applied.append(
                (
                    candidate.publishing.news.first_review_model,
                    candidate.publishing.news.second_review_model,
                )
            )

        changed = await manager.refresh(apply)
        assert changed is manager.current
        assert history.last_active().revision == changed.revision

    try:
        asyncio.run(scenario())
        assert applied == [("deepseek-v4-flash", "deepseek-v4-pro")]
    finally:
        database.close()


def test_invalid_live_edit_keeps_last_active_snapshot(tmp_path: Path) -> None:
    config_root, database, history, manager, _reports = _setup(tmp_path)

    async def scenario() -> None:
        initial, _ = await manager.load_initial()
        (config_root / "sources.yaml").write_text("version: 1\nsources: [", encoding="utf-8")
        with pytest.raises(ConfigurationError):
            await manager.refresh(lambda _old, _new: asyncio.sleep(0))
        assert manager.current is initial
        assert history.last_active().revision == initial.revision
        assert await manager.refresh(lambda _old, _new: asyncio.sleep(0)) is None

    try:
        asyncio.run(scenario())
    finally:
        database.close()


def test_invalid_files_on_restart_fall_back_to_last_active_revision(tmp_path: Path) -> None:
    config_root, database, history, first_manager, _reports = _setup(tmp_path)

    async def scenario() -> None:
        initial, _ = await first_manager.load_initial()
        (config_root / "publishing.yaml").write_text("not: valid", encoding="utf-8")

        async def preflight(snapshot):
            return {"ok": True, "fallback": snapshot.revision}

        restarted = ConfigManager(config_root, history, preflight, debounce_seconds=0)
        restored, degraded = await restarted.load_initial()
        assert degraded is True
        assert restored.revision == initial.revision
        assert restarted.current is restored

    try:
        asyncio.run(scenario())
    finally:
        database.close()


def test_failed_apply_does_not_activate_candidate(tmp_path: Path) -> None:
    config_root, database, history, manager, _reports = _setup(tmp_path)

    async def scenario() -> None:
        initial, _ = await manager.load_initial()
        _change_publish_interval(config_root, 17)

        async def fail_apply(_previous, _candidate):
            raise RuntimeError("component swap failed")

        with pytest.raises(RuntimeError, match="swap failed"):
            await manager.refresh(fail_apply)
        assert manager.current is initial
        assert history.last_active().revision == initial.revision

    try:
        asyncio.run(scenario())
    finally:
        database.close()
