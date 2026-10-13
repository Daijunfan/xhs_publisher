from __future__ import annotations

import json
import plistlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from xhs_local import cli
from xhs_local.core.states import WorkState, WorkTopic
from xhs_local.storage.database import Database
from xhs_local.storage.dead_letters import DeadLetterRepository
from xhs_local.storage.schema import migrate
from xhs_local.storage.work_items import WorkItemRepository


def snapshot(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        runtime_root=tmp_path / "runtime",
        database_path=tmp_path / "runtime/app.sqlite3",
        app=SimpleNamespace(
            sqlite=SimpleNamespace(busy_timeout_seconds=30),
            timezone="Asia/Shanghai",
        ),
        publishing=SimpleNamespace(
            news=SimpleNamespace(
                publish_interval_minutes=20,
                night_publish_interval_minutes=45,
            )
        ),
    )


def test_render_plist_is_atomic_python_only_and_never_bootstraps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = snapshot(tmp_path)
    monkeypatch.setattr(cli, "_snapshot", lambda: state)
    monkeypatch.setattr(
        cli,
        "_launchctl",
        lambda *_args, **_kwargs: pytest.fail("plist rendering must not call launchctl"),
    )
    destination = tmp_path / "LaunchAgents/com.xhs-local.pipeline.plist"
    rendered = cli._render_plist(  # noqa: SLF001
        destination=destination,
        project_root=tmp_path,
        python_executable=Path(sys.executable),
    )
    assert rendered == destination.resolve()
    with destination.open("rb") as stream:
        payload = plistlib.load(stream)
    assert payload["Label"] == "com.xhs-local.pipeline"
    assert payload["ProgramArguments"] == [
        str(Path(sys.executable).absolute()),
        "-m",
        "xhs_local",
        "run",
    ]
    assert payload["WorkingDirectory"] == str(tmp_path.resolve())
    assert payload["KeepAlive"] is True
    assert payload["ProcessType"] == "Interactive"
    assert "/opt/homebrew/bin" in payload["EnvironmentVariables"]["PATH"].split(":")
    assert payload["StandardOutPath"] == str(state.runtime_root / "logs/launchd.log")
    assert not list(destination.parent.glob(".*.tmp"))


def test_render_plist_rejects_a_missing_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_snapshot", lambda: snapshot(tmp_path))
    with pytest.raises(RuntimeError, match="Python executable"):
        cli._render_plist(  # noqa: SLF001
            destination=tmp_path / "agent.plist",
            project_root=tmp_path,
            python_executable=tmp_path / "missing-python",
        )


def test_default_plist_preserves_the_virtualenv_python_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_snapshot", lambda: snapshot(tmp_path))
    executable = tmp_path / ".venv/bin/python"
    executable.parent.mkdir(parents=True)
    executable.symlink_to(Path(sys.executable))

    destination = cli._render_plist(  # noqa: SLF001
        destination=tmp_path / "agent.plist",
        project_root=tmp_path,
    )

    with destination.open("rb") as stream:
        payload = plistlib.load(stream)
    assert payload["ProgramArguments"][0] == str(executable)


def test_start_retries_launchd_bootstrap_race(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.sys, "platform", "darwin")
    calls = []
    bootstrap_attempts = 0

    def launchctl(*arguments: str, check: bool = True):
        nonlocal bootstrap_attempts
        del check
        calls.append(arguments)
        if arguments[0] == "print":
            return subprocess.CompletedProcess(arguments, 1, "", "not loaded")
        if arguments[0] == "bootstrap":
            bootstrap_attempts += 1
            if bootstrap_attempts == 1:
                return subprocess.CompletedProcess(
                    arguments,
                    5,
                    "",
                    "Bootstrap failed: 5: Input/output error",
                )
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(cli, "_render_plist", lambda: None)
    monkeypatch.setattr(cli, "_launchctl", launchctl)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    assert cli.start() == 0
    assert bootstrap_attempts == 2
    assert [call[0] for call in calls] == ["print", "bootstrap", "bootstrap"]


def test_start_never_restarts_an_already_registered_service(monkeypatch):
    monkeypatch.setattr(cli.sys, "platform", "darwin")
    calls = []

    def launchctl(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(cli, "_render_plist", lambda: None)
    monkeypatch.setattr(cli, "_launchctl", launchctl)
    assert cli.start() == 0
    assert [call[0] for call in calls] == ["print", "kickstart"]
    assert all("-k" not in call and "bootout" not in call for call in calls)


def test_linux_start_and_stop_use_user_service(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.sys, "platform", "linux")

    def run(args):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(cli.subprocess, "run", run)
    assert cli.start() == cli.stop() == 0
    assert calls == [
        ["systemctl", "--user", "start", "xhs-cloud.service"],
        ["systemctl", "--user", "stop", "xhs-cloud.service"],
    ]


def test_migrate_command_uses_snapshot_database_and_runs_quick_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    state = snapshot(tmp_path)
    observed: dict[str, object] = {}

    class FakeDatabase:
        def __init__(self, path: Path, *, busy_timeout_seconds: float) -> None:
            observed["path"] = path
            observed["timeout"] = busy_timeout_seconds

        def __enter__(self) -> FakeDatabase:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        @staticmethod
        def quick_check() -> None:
            observed["quick_check"] = True

    monkeypatch.setattr(cli, "_snapshot", lambda: state)
    monkeypatch.setattr(cli, "Database", FakeDatabase)
    monkeypatch.setattr(cli, "migrate", lambda database: 3)
    assert cli.main(["migrate"]) == 0
    assert observed == {
        "path": state.database_path,
        "timeout": 30,
        "quick_check": True,
    }
    assert "database schema ready: version=3" in capsys.readouterr().out


def test_status_is_read_only_for_running_stale_and_invalid_pid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    state = snapshot(tmp_path)
    monkeypatch.setattr(cli, "_snapshot", lambda: state)
    kills: list[tuple[int, int]] = []
    monkeypatch.setattr(cli.os, "kill", lambda pid, signal: kills.append((pid, signal)))
    monkeypatch.setattr(
        cli,
        "read_status",
        lambda _path: {
            "pid": 4321,
            "ready": True,
            "started_at": "2026-08-19T18:00:00+08:00",
            "config_revision": "abc",
            "queues": {},
            "source_targets": {},
            "news_scheduling": {
                "pending_candidates": 0,
                "threshold": 7,
                "scheduled_publish_interval_minutes": 15,
                "scheduled_publish_next_at": "2026-08-19T18:15:00+08:00",
            },
            "source_news_scheduling": {
                "telegram": {
                    "mode": "capacity",
                    "batch_size": 18,
                    "immediate_five_star": True,
                    "publish_interval_minutes": 15,
                },
                "x": {
                    "mode": "capacity",
                    "batch_size": 18,
                    "immediate_five_star": True,
                    "publish_interval_minutes": 30,
                },
            },
            "work_states": {},
            "dead_letters": 0,
            "remote_ambiguous": 0,
        },
    )
    assert cli.main(["status"]) == 0
    output = capsys.readouterr().out
    assert "服务状态：正常运行" in output
    assert "PID 4321" in output
    assert "待处理 0 条" in output
    assert "每 15 分钟全平台排序发布｜同平台成帖｜五星单独成帖" in output
    assert "最近未发现 ERROR/CRITICAL" in output
    assert cli.main(["status", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["pid"] == 4321
    assert kills == [(4321, 0), (4321, 0)]

    monkeypatch.setattr(cli, "read_status", lambda _path: {"pid": -1})
    assert cli.main(["status"]) == 0
    assert "服务状态：已停止" in capsys.readouterr().out
    assert kills == [(4321, 0), (4321, 0)]

    def stale(_pid: int, _signal: int) -> None:
        raise ProcessLookupError

    monkeypatch.setattr(cli.os, "kill", stale)
    monkeypatch.setattr(cli, "read_status", lambda _path: {"pid": 9876})
    assert cli.main(["status"]) == 0
    assert "状态文件已过期" in capsys.readouterr().out


def test_status_summary_uses_persisted_last_round_after_restart(tmp_path: Path) -> None:
    state = snapshot(tmp_path)
    state.database_path.parent.mkdir(parents=True)
    with Database(state.database_path) as database:
        migrate(database)
        with database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO publish_slots(
                    slot_start,slot_end,status,started_at,completed_at,item_count
                ) VALUES(?,?,?,?,?,?)
                """,
                (
                    "2026-08-19T09:55:00.000Z",
                    "2026-08-19T10:00:00.000Z",
                    "published",
                    "2026-08-19T10:00:00.000Z",
                    "2026-08-19T10:00:30.000Z",
                    2,
                ),
            )
    output = cli._format_status_summary(  # noqa: SLF001
        state,
        {
            "pid": 4321,
            "started_at": "2026-08-19T17:50:00+08:00",
            "source_targets": {},
            "news_scheduling": {"pending_candidates": 0, "threshold": 7},
            "queues": {},
            "work_states": {},
            "dead_letters": 0,
            "remote_ambiguous": 0,
        },
    )
    assert "2026-08-19 18:00:30，已发布" in output


def test_recover_and_audited_dlq_commands_are_non_interactive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    state = snapshot(tmp_path)
    state.database_path.parent.mkdir(parents=True)
    with Database(state.database_path) as database:
        migrate(database)
        works = WorkItemRepository(database)
        interrupted_id = works.create(WorkTopic.NEWS_PUBLISH)
        assert works.claim(interrupted_id) is not None
        dead_id = works.create(WorkTopic.RECORD_COLLECTED)
        assert works.claim(dead_id) is not None
        letter_id = DeadLetterRepository(database).move(
            dead_id,
            error_class="PLUGIN_BUG",
            error_summary="fixture failure",
        )

    monkeypatch.setattr(cli, "_snapshot", lambda: state)
    monkeypatch.setattr(cli, "_running_pid", lambda: None)
    assert cli.main(["recover"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["work_items"]["ready"] == 1

    assert cli.main(["dlq", "list"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["dead_letter_id"] == letter_id
    assert cli.main(["dlq", "replay", letter_id, "--actor", "owner", "--reason", "fixed"]) == 0
    assert capsys.readouterr().out.strip()
    with Database(state.database_path) as database:
        assert WorkItemRepository(database).get(dead_id).state is WorkState.READY
