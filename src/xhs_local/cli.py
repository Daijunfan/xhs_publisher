"""Operator CLI for the local single-process application."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import plistlib
import sqlite3
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from xhs_local.app import CONFIG_ROOT, PROJECT_ROOT, run_application
from xhs_local.configuration.history import ConfigHistory
from xhs_local.configuration.loader import load_snapshot
from xhs_local.core.states import WorkState
from xhs_local.observability.status import read_status
from xhs_local.plugins.registry import SourcePluginRegistry
from xhs_local.plugins.sources.telegram.client import authorize_telegram_session
from xhs_local.storage.backups import BackupService
from xhs_local.storage.database import Database
from xhs_local.storage.dead_letters import DeadLetterRepository
from xhs_local.storage.outbox import OutboxRepository
from xhs_local.storage.schema import assert_current, migrate, open_database
from xhs_local.storage.work_items import WorkItemRepository

LAUNCHD_LABEL = "com.xhs-local.pipeline"
LAUNCH_AGENTS = Path.home() / "Library/LaunchAgents"
LAUNCHD_PATH = LAUNCH_AGENTS / f"{LAUNCHD_LABEL}.plist"
BEIJING = ZoneInfo("Asia/Shanghai")
OUTCOME_LABELS = {
    "published": "已发布",
    "filtered": "筛选完成，无合格内容",
    "empty": "没有候选帖子",
    "not_submitted": "提交前失败，等待重试",
    "ambiguous": "提交结果待确认",
    "rate_limited": "今日发布已达上限，明日自动恢复",
    "rate-limited": "今日发布已达上限，明日自动恢复",
    "rejected": "远端明确拒绝，本批已跳过",
    "publish-failed": "提交后未在笔记管理页确认",
    "paused": "发布已暂停",
    "duplicate": "重复任务已跳过",
    "deferred": "五星检查完成，非五星内容继续积累",
    "error": "处理失败",
}


def _snapshot():
    return load_snapshot(CONFIG_ROOT)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BEIJING)
    return parsed.astimezone(BEIJING)


def _display_time(value: object, *, include_date: bool = True) -> str:
    parsed = _parse_time(value)
    if parsed is None:
        return "暂无"
    pattern = "%Y-%m-%d %H:%M:%S" if include_date else "%H:%M:%S"
    return parsed.strftime(pattern)


def _duration_since(value: object) -> str:
    started = _parse_time(value)
    if started is None:
        return "未知"
    seconds = max(0, int((datetime.now(BEIJING) - started).total_seconds()))
    hours, remainder = divmod(seconds, 3600)
    minutes, _seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}小时{minutes}分钟"
    return f"{minutes}分钟"


def _localize_times(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {name: _localize_times(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [_localize_times(item, key) for item in value]
    if key.endswith("_at") or key in {"started_at", "updated_at", "cooldown_until"}:
        parsed = _parse_time(value)
        return parsed.isoformat() if parsed is not None else value
    return value


def _database_status(database_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"confirmed_posts": 0, "today_confirmed_posts": 0, "latest_slot": None}
    try:
        connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            result["confirmed_posts"] = int(
                connection.execute(
                    """
                    SELECT count(*) FROM remote_operations
                     WHERE sink='xiaohongshu' AND state='SUCCEEDED'
                       AND json_extract(result_json,'$.confirmed_in_note_manager')=1
                    """
                ).fetchone()[0]
            )
            day_start = (
                datetime.now(BEIJING)
                .replace(
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                .astimezone(UTC)
            )
            result["today_confirmed_posts"] = int(
                connection.execute(
                    """
                    SELECT count(*) FROM remote_operations
                     WHERE sink='xiaohongshu' AND state='SUCCEEDED'
                       AND json_extract(result_json,'$.confirmed_in_note_manager')=1
                       AND datetime(updated_at)>=datetime(?)
                    """,
                    (day_start.isoformat(),),
                ).fetchone()[0]
            )
            row = connection.execute(
                """
                SELECT status,item_count,completed_at,error FROM publish_slots
                 ORDER BY started_at DESC LIMIT 1
                """
            ).fetchone()
            result["latest_slot"] = None if row is None else dict(row)
        finally:
            connection.close()
    except (OSError, sqlite3.Error):
        pass
    return result


def _recent_log_status(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"error_count": 0, "last_error": None}
    try:
        with path.open("rb") as stream:
            size = stream.seek(0, os.SEEK_END)
            stream.seek(max(0, size - 256 * 1024))
            payload = stream.read().decode(errors="replace")
    except OSError:
        return result
    for line in payload.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("level") not in {"ERROR", "CRITICAL"}:
            continue
        result["error_count"] += 1
        result["last_error"] = event
    return result


def _format_status_summary(snapshot: Any, state: dict[str, Any]) -> str:
    if state.get("mode") == "website":
        targets = list((state.get("source_targets") or {}).values())
        healthy = sum(bool(target.get("last_success_at")) for target in targets)
        failed = sum(bool(target.get("failures")) for target in targets)
        port = state["website"]["port"]
        return (
            f"本地新闻网站：{'运行中' if state.get('ready') else '已停止'} · 端口 {port}\n"
            f"采集目标：{len(targets)} · 本次启动已成功 {healthy} · 当前有错误 {failed}\n"
            "发布方式：本地展示；AI Agent 审核、撰写并调用小红书发布 API"
        )
    targets = list((state.get("source_targets") or {}).values())
    healthy = sum(
        1
        for target in targets
        if target.get("enabled") and not target.get("failures") and target.get("last_success_at")
    )
    failures = [
        str(target.get("target_id") or target.get("source_id") or "未知目标")
        for target in targets
        if target.get("failures")
    ]
    recent_successes = [
        parsed
        for parsed in (_parse_time(target.get("last_success_at")) for target in targets)
        if parsed is not None
    ]
    last_collection = max(recent_successes).strftime("%H:%M:%S") if recent_successes else "暂无"
    scheduling = state.get("news_scheduling") or {}
    source_scheduling = state.get("source_news_scheduling") or {}
    pending = int(scheduling.get("pending_candidates") or 0)
    threshold = int(scheduling.get("threshold") or 0)
    next_time = (
        scheduling.get("cooldown_until")
        or scheduling.get("next_check_at")
        or scheduling.get("scheduled_publish_next_at")
    )
    next_label = "冷却至" if scheduling.get("cooldown_until") else "下次检查"
    if next_time:
        next_text = f"{next_label} {_display_time(next_time, include_date=False)}"
    else:
        next_text = "等待调度"
    initialization = state.get("news_initialization") or {}
    if initialization.get("state") in {"waiting_for_sources", "running"}:
        next_text = "恢复补发中（各平台最多一篇）"
    elif (state.get("news_network_recovery") or {}).get("since"):
        next_text = "网络恢复等待中（待发保留，自动重试）"
    queues = state.get("queues") or {}
    queue_total = sum(int(item.get("size") or 0) for item in queues.values())
    work_states = state.get("work_states") or {}
    pending_work = sum(
        int(work_states.get(name) or 0)
        for name in ("READY", "RUNNING", "SUBMITTING", "RETRY_WAIT", "WAITING_OPERATOR")
    )
    database = _database_status(snapshot.database_path)
    logs = _recent_log_status(snapshot.runtime_root / "logs" / "pipeline.jsonl")
    latest_slot = database.get("latest_slot") or {}
    state_outcome = state.get("last_news_round_outcome")
    outcome_key = str(state_outcome or latest_slot.get("status") or "")
    outcome = OUTCOME_LABELS.get(outcome_key, "尚未执行")
    last_round_value = state.get("last_news_round_at") or latest_slot.get("completed_at")
    last_round = _display_time(last_round_value)
    interval = snapshot.publishing.news.publish_interval_minutes
    night_interval = snapshot.publishing.news.night_publish_interval_minutes
    if source_scheduling:
        scheduled_minutes = float(scheduling.get("scheduled_publish_interval_minutes") or interval)
        schedule_policy = f"每 {scheduled_minutes:g} 分钟全平台排序发布｜同平台成帖｜五星单独成帖"
    else:
        schedule_policy = (
            f"阈值 {threshold} 条｜日间 {interval:g} 分钟｜夜间 {night_interval:g} 分钟"
        )
    dead_letters = int(state.get("dead_letters") or 0)
    ambiguous = int(state.get("remote_ambiguous") or 0)
    today_confirmed = database["today_confirmed_posts"]
    daily_text = f"今日确认 {today_confirmed} 条"
    lines = [
        "服务状态：正常运行",
        (
            f"进程：PID {state['pid']}｜启动 {_display_time(state.get('started_at'))} "
            f"（已运行 {_duration_since(state.get('started_at'))}）"
        ),
        f"采集：{healthy}/{len(targets)} 个目标正常｜最近成功 {last_collection}",
        f"调度：待处理 {pending} 条｜{schedule_policy}｜{next_text}",
        (
            f"发布：最近一轮 {last_round}，{outcome}｜"
            f"{daily_text}｜"
            f"累计确认 {database['confirmed_posts']} 条"
        ),
        (
            f"任务：队列 {queue_total}｜处理中 {pending_work}｜"
            f"死信 {dead_letters}｜待确认/限流 {ambiguous}"
        ),
    ]
    if failures:
        lines.append(f"异常目标：{', '.join(failures[:3])}")
    if logs["last_error"] is None:
        lines.append("日志：最近未发现 ERROR/CRITICAL")
    else:
        event = logs["last_error"]
        event_name = event.get("event", "未知错误")
        event_time = _display_time(event.get("timestamp"))
        lines.append(f"日志：最近错误 {event_time}｜{event_name}")
    lines.append("完整详情：xhs status --json")
    return "\n".join(lines)


def _render_plist(
    *,
    destination: Path | None = None,
    project_root: Path | None = None,
    python_executable: Path | None = None,
) -> Path:
    """Atomically render launchd configuration without invoking launchctl."""

    snapshot = _snapshot()
    root = (project_root or PROJECT_ROOT).resolve()
    executable = Path(
        os.path.abspath((python_executable or (root / ".venv/bin/python")).expanduser())
    )
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise RuntimeError(f"Python executable is unavailable: {executable}")
    output_path = (destination or LAUNCHD_PATH).expanduser().resolve()
    log_dir = snapshot.runtime_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    template_path = PROJECT_ROOT / "ops" / f"{LAUNCHD_LABEL}.plist"
    with template_path.open("rb") as stream:
        payload = plistlib.load(stream)
    if payload.get("Label") != LAUNCHD_LABEL:
        raise RuntimeError(f"launchd template has the wrong label: {template_path}")
    payload.update(
        {
            "ProgramArguments": [str(executable), "-m", "xhs_local", "run"],
            "WorkingDirectory": str(root),
            "StandardOutPath": str(log_dir / "launchd.log"),
            "StandardErrorPath": str(log_dir / "launchd.log"),
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as stream:
        plistlib.dump(payload, stream, sort_keys=True)
    temporary.replace(output_path)
    return output_path


def _launchctl(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["launchctl", *arguments],
        text=True,
        capture_output=True,
        check=check,
        timeout=30 if arguments and arguments[0] == "bootout" else 10,
    )


def start() -> int:
    if sys.platform == "linux":
        return subprocess.run(["systemctl", "--user", "start", "xhs-cloud.service"]).returncode
    _render_plist()
    domain = f"gui/{os.getuid()}"
    target = f"{domain}/{LAUNCHD_LABEL}"
    if _launchctl("print", target, check=False).returncode == 0:
        result = _launchctl("kickstart", target, check=False)
        if result.returncode:
            print(result.stderr.strip(), file=sys.stderr)
            return result.returncode
        print("pipeline already registered; ensured running without restarting it")
        return 0
    result = None
    for attempt in range(3):
        result = _launchctl("bootstrap", domain, str(LAUNCHD_PATH), check=False)
        if result.returncode == 0 or "already bootstrapped" in result.stderr.lower():
            break
        if attempt < 2 and "input/output error" in result.stderr.lower():
            time.sleep(0.25)
            continue
        break
    assert result is not None
    if result.returncode != 0 and "already bootstrapped" not in result.stderr.lower():
        print(result.stderr.strip(), file=sys.stderr)
        return result.returncode or 1
    # RunAtLoad starts the freshly registered job. Never kill it a second time.
    print(f"pipeline started via launchd ({LAUNCHD_LABEL})")
    return 0


def stop() -> int:
    if sys.platform == "linux":
        return subprocess.run(["systemctl", "--user", "stop", "xhs-cloud.service"]).returncode
    target = f"gui/{os.getuid()}/{LAUNCHD_LABEL}"
    result = _launchctl("bootout", target, check=False)
    if result.returncode != 0 and "could not find" not in result.stderr.lower():
        print(result.stderr.strip(), file=sys.stderr)
        return result.returncode or 1
    print("pipeline stopped")
    return 0


def status(*, json_output: bool = False) -> int:
    snapshot = _snapshot()
    state = read_status(snapshot.runtime_root / "status.json")
    if (
        not state
        or not isinstance(state.get("pid"), int)
        or isinstance(state.get("pid"), bool)
        or state["pid"] <= 1
    ):
        print("服务状态：已停止")
        return 0
    pid = state["pid"]
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        print("服务状态：已停止（状态文件已过期）")
        return 0
    if json_output:
        print(
            json.dumps(
                _localize_times(state),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(_format_status_summary(snapshot, state))
    return 0


def _running_pid() -> int | None:
    snapshot = _snapshot()
    state = read_status(snapshot.runtime_root / "status.json")
    pid = state.get("pid") if state else None
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 1:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    return pid


def migrate_database() -> int:
    snapshot = _snapshot()
    with Database(
        snapshot.database_path,
        busy_timeout_seconds=snapshot.app.sqlite.busy_timeout_seconds,
    ) as database:
        version = migrate(database)
        database.quick_check()
    print(f"database schema ready: version={version}, path={snapshot.database_path}")
    return 0


async def check() -> int:
    snapshot = _snapshot()
    with open_database(
        snapshot.database_path,
        busy_timeout_seconds=snapshot.app.sqlite.busy_timeout_seconds,
    ) as database:
        assert_current(database)
        database.quick_check()
    registry = SourcePluginRegistry()
    for source in snapshot.sources.sources:
        if not source.enabled:
            continue
        prepared = registry.prepare(
            source,
            config_root=snapshot.config_root,
            runtime_root=snapshot.runtime_root,
        )
        await registry.preflight(prepared, healthcheck=True)
    print("preflight passed: SQLite and sources; AI Agent owns review, writing and publish API")
    return 0


async def authorize_telegram() -> int:
    snapshot = _snapshot()
    source = next(item for item in snapshot.sources.sources if item.plugin == "telegram")
    await authorize_telegram_session(snapshot.resolve(str(source.options["session_path"])))
    return 0


def backup() -> int:
    snapshot = _snapshot()
    with open_database(snapshot.database_path) as database:
        result = BackupService(database).create(
            snapshot.runtime_root / "backups",
            config_paths=tuple(
                CONFIG_ROOT / name for name in ("app.yaml", "sources.yaml", "publishing.yaml")
            ),
        )
    print(result.database_path)
    return 0


def recover() -> int:
    pid = _running_pid()
    if pid is not None:
        raise RuntimeError(f"stop the pipeline before explicit recovery (pid={pid})")
    snapshot = _snapshot()
    with open_database(
        snapshot.database_path,
        busy_timeout_seconds=snapshot.app.sqlite.busy_timeout_seconds,
    ) as database:
        works = WorkItemRepository(database)
        outbox = OutboxRepository(database)
        report = {
            "work_items": works.recover_interrupted(),
        }
        ready_ids = works.recoverable_ids(states=(WorkState.READY,))
        report["outbox_restored"] = outbox.restore_for_works(ready_ids)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


def dlq_list() -> int:
    snapshot = _snapshot()
    with open_database(snapshot.database_path) as database:
        rows = [
            _localize_times(asdict(item)) for item in DeadLetterRepository(database).list_open()
        ]
    print(json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def dlq_replay(dead_letter_id: str, *, actor: str, reason: str) -> int:
    pid = _running_pid()
    if pid is not None:
        raise RuntimeError(f"stop the pipeline before replaying a dead letter (pid={pid})")
    snapshot = _snapshot()
    with open_database(snapshot.database_path) as database:
        event_id = DeadLetterRepository(database).replay(
            dead_letter_id,
            actor=actor,
            reason=reason,
        )
    print(event_id)
    return 0


def config_history() -> int:
    snapshot = _snapshot()
    with open_database(snapshot.database_path) as database:
        history = ConfigHistory(
            database,
            snapshot.runtime_root / "config-history",
            CONFIG_ROOT,
        )
        print(
            json.dumps(
                _localize_times(history.revisions()),
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


def config_rollback(revision: str) -> int:
    snapshot = _snapshot()
    with open_database(snapshot.database_path) as database:
        history = ConfigHistory(
            database,
            snapshot.runtime_root / "config-history",
            CONFIG_ROOT,
        )
        restored = history.rollback_files(revision)
    print(f"configuration files restored to {restored.revision}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="xhs")
    sub = parser.add_subparsers(dest="command", required=True)
    commands = (
        "run",
        "start",
        "stop",
        "check",
        "migrate",
        "backup",
        "recover",
        "telegram-authorize",
    )
    for name in commands:
        sub.add_parser(name)
    status_command = sub.add_parser("status")
    status_command.add_argument("--json", action="store_true", dest="json_output")
    config = sub.add_parser("config")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("history")
    rollback = config_sub.add_parser("rollback")
    rollback.add_argument("revision")
    dlq = sub.add_parser("dlq")
    dlq_sub = dlq.add_subparsers(dest="dlq_command", required=True)
    dlq_sub.add_parser("list")
    replay = dlq_sub.add_parser("replay")
    replay.add_argument("dead_letter_id")
    replay.add_argument("--actor", default="local-owner")
    replay.add_argument("--reason", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "run":
        asyncio.run(run_application())
        return 0
    if args.command == "start":
        return start()
    if args.command == "stop":
        return stop()
    if args.command == "status":
        return status(json_output=args.json_output)
    if args.command == "check":
        return asyncio.run(check())
    if args.command == "migrate":
        return migrate_database()
    if args.command == "backup":
        return backup()
    if args.command == "recover":
        return recover()
    if args.command == "telegram-authorize":
        return asyncio.run(authorize_telegram())
    if args.command == "dlq":
        if args.dlq_command == "list":
            return dlq_list()
        return dlq_replay(
            args.dead_letter_id,
            actor=args.actor,
            reason=args.reason,
        )
    if args.config_command == "history":
        return config_history()
    return config_rollback(args.revision)
