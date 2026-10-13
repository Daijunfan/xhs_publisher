from __future__ import annotations

import asyncio
import inspect
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from xhs_local.core.contracts import PublishNote
from xhs_local.plugins.sinks.xiaohongshu import browser
from xhs_local.plugins.sinks.xiaohongshu.backend import (
    SafariAppleScriptBackend,
    reconcile_note_history,
)
from xhs_local.plugins.sinks.xiaohongshu.browser import (
    SafariPublisher,
    SafariPublishError,
    SafariSession,
)
from xhs_local.plugins.sinks.xiaohongshu.errors import SubmissionRejectedError
from xhs_local.plugins.sinks.xiaohongshu.macos import SafariTabSession
from xhs_local.plugins.sinks.xiaohongshu.models import (
    BackendPublishRequest,
    BackendPublishResult,
    BackendPublishStatus,
)


class ScriptSession:
    def __init__(self, *responses: dict[str, object]) -> None:
        self.responses = list(responses)
        self.scripts: list[str] = []

    def run_javascript(self, source: str) -> str:
        self.scripts.append(source)
        return json.dumps(self.responses.pop(0))


@pytest.mark.parametrize(
    "text,total,expected",
    [
        ("全部 20\n模型升级\n2026-09-19 10:01\n", 20, True),
        ("全部 20\n模型升级\n2026-09-19 09:59\n", 20, False),
        ("全部 20\n其他新消息\n2026-09-19 10:10\n", 20, None),
        ("全部 20\n其他新消息\n2026-09-19 10:10\n旧消息\n2026-09-19 09:59\n", 20, False),
        ("全部 0\n", 0, None),  # A loading placeholder or offline page is NOT absence proof.
    ],
)
def test_reconciliation_requires_dated_evidence_not_fuzzy_titles(text, total, expected):
    result = reconcile_note_history(
        text,
        title="模型升级",
        body="",
        created_at="2026-09-19T02:00:30+00:00",
        total=total,
        now=datetime(2026, 9, 19, 2, 20, tzinfo=UTC),
    )
    assert result["found"] is expected


def test_recent_unseen_submission_is_not_retried_before_consistency_grace():
    result = reconcile_note_history(
        "全部 20\n旧消息\n2026-09-19 09:59\n",
        title="模型升级",
        body="",
        total=20,
        created_at="2026-09-19T02:00:30+00:00",
        now=datetime(2026, 9, 19, 2, 1, tzinfo=UTC),
    )
    assert result["found"] is None


def image(tmp_path: Path, name: str = "card.png") -> Path:
    path = tmp_path / name
    path.write_bytes(b"image-bytes")
    return path


def test_internal_request_preserves_empty_resource_notes_topics_and_gif(tmp_path: Path) -> None:
    request = BackendPublishRequest(
        title="",
        body="",
        image_paths=(image(tmp_path, "motion.gif"),),
        topics=("人工智能", "开源"),
        allow_empty_text=True,
    )

    request.validate()

    assert request.effective_body == ""


def test_news_summary_caption_and_topics_reach_the_safari_adapter_unchanged(tmp_path):
    note = PublishNote(
        "模型性能更新",
        "模型推理速度翻倍。\n开源工具新增性能分析功能。",
        (image(tmp_path),),
        topics=("人工智能", "开源"),
    )
    request = SafariPublisher(max_images=18)._request(note, require_new_title_occurrence=False)  # noqa: SLF001
    assert request.title == note.title
    assert request.topics == note.topics
    assert request.effective_body == (
        " ".join(note.body.split()) if sys.platform == "linux" else note.body
    )
    session = ScriptSession(
        {"title": note.title, "body": note.body}, {"title": note.title, "body": note.body}
    )
    backend = SafariAppleScriptBackend()
    backend._session = session  # noqa: SLF001
    backend._fill_note(note.title, note.body)  # noqa: SLF001
    assert all(json.dumps(note.body, ensure_ascii=True) in script for script in session.scripts)


@pytest.mark.parametrize(
    ("title", "body", "allow_empty", "message"),
    [
        ("", "正文", False, "title"),
        ("标题", "", False, "body"),
        ("123456789012345678901", "正文", False, "title"),
    ],
)
def test_internal_request_rejects_invalid_text(
    tmp_path: Path,
    title: str,
    body: str,
    allow_empty: bool,
    message: str,
) -> None:
    request = BackendPublishRequest(
        title=title,
        body=body,
        image_paths=(image(tmp_path),),
        allow_empty_text=allow_empty,
    )

    with pytest.raises(RuntimeError, match=message):
        request.validate()


def test_backend_injects_images_and_fills_fields_from_proven_source(tmp_path: Path) -> None:
    session = ScriptSession(
        {"selected": 1},
        {"title": "标题", "body": "正文"},
        {"title": "标题", "body": "正文"},
    )
    backend = SafariAppleScriptBackend()
    backend._session = session  # type: ignore[assignment]  # noqa: SLF001

    backend._upload_images((image(tmp_path),))  # noqa: SLF001
    backend._fill_note("标题", "正文")  # noqa: SLF001

    assert "new DataTransfer()" in session.scripts[0]
    assert "input.dispatchEvent(new Event('change'" in session.scripts[0]
    assert "HTMLInputElement.prototype, 'value'" in session.scripts[1]
    assert "document.execCommand('insertText'" in session.scripts[1]
    assert session.scripts[1] == session.scripts[2]


def test_backend_dispatches_component_publish_event_without_private_method() -> None:
    session = ScriptSession({"submitted": True})
    backend = SafariAppleScriptBackend()
    backend._session = session  # type: ignore[assignment]  # noqa: SLF001

    backend._submit_note()  # noqa: SLF001

    script = session.scripts[0]
    assert "dispatchEvent(new CustomEvent('publish'" in script
    assert "_onPublish" not in script
    assert "Math.random" not in script
    assert "mousemove" not in script


def test_note_manager_parser_uses_title_and_total_proofs() -> None:
    session = ScriptSession(
        {
            "loaded": True,
            "found": True,
            "count": 1,
            "total": 9,
            "excerpt": "标题 2026-08-28",
        }
    )
    backend = SafariAppleScriptBackend()
    backend._session = session  # type: ignore[assignment]  # noqa: SLF001

    result = backend._read_manager("标题", minimum_total=9)  # noqa: SLF001

    assert result["found"] is True
    assert "minimumTotal" in session.scripts[0]
    assert "bestScore >= .45" in session.scripts[0]
    assert "targetGrams" in session.scripts[0]
    assert "titleProof || countGrowth" in session.scripts[0]


def test_every_publish_requires_note_count_growth_and_title_reconciliation() -> None:
    source = inspect.getsource(SafariAppleScriptBackend.publish)

    assert "_ensure_session(NOTE_MANAGER_URL)" in source
    assert "_read_note_baseline" in source
    assert "minimum_total=baseline + 1" in source
    assert 'current["uploading_count"] == 0' in source


def test_note_baseline_reuses_the_manager_state_that_was_already_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = SafariAppleScriptBackend()
    monkeypatch.setattr(backend, "_navigate", lambda _url: None)
    monkeypatch.setattr(
        backend,
        "_wait_for_manager",
        lambda _timeout: {"loaded": True, "total": 12},
    )
    monkeypatch.setattr(
        backend,
        "_read_manager",
        lambda *_args, **_kwargs: pytest.fail("baseline must not reread the changing page"),
    )

    assert backend._read_note_baseline(1) == 12  # noqa: SLF001


def test_state_probe_tracks_background_image_uploads() -> None:
    source = inspect.getsource(SafariAppleScriptBackend._read_state)  # noqa: SLF001

    assert ".mask.uploading, .progress-container" in source
    assert "uploading_count" in source


def test_unchanged_note_count_is_an_explicit_remote_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = SafariAppleScriptBackend()
    monkeypatch.setattr(backend, "_navigate", lambda _url: None)
    monkeypatch.setattr(backend, "_wait_for_manager", lambda _timeout: None)
    monkeypatch.setattr(
        backend,
        "_read_manager",
        lambda _title, *, minimum_total: {
            "loaded": True,
            "found": False,
            "total": minimum_total - 1,
        },
    )
    monkeypatch.setattr(
        "xhs_local.plugins.sinks.xiaohongshu.backend.time.sleep",
        lambda _seconds: None,
    )

    with pytest.raises(SubmissionRejectedError, match="total did not increase"):
        backend._confirm_note("标题", minimum_total=8, timeout=0.01)  # noqa: SLF001


def test_async_adapter_maps_success_to_project_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SuccessfulBackend:
        def publish(self, request: BackendPublishRequest) -> BackendPublishResult:
            request.validate()
            return BackendPublishResult(
                BackendPublishStatus.PUBLISHED,
                "https://creator.xiaohongshu.com/creator/notemanage",
                "confirmed",
                "标题 2026-08-28",
            )

    monkeypatch.setattr(browser, "SafariAppleScriptBackend", SuccessfulBackend)
    publisher = SafariPublisher(max_images=18, session=SafariSession())

    result = asyncio.run(
        publisher.publish(
            PublishNote(
                "标题",
                "正文",
                (image(tmp_path),),
                topics=("人工智能",),
            )
        )
    )

    assert result.ok is True
    assert result.confirmed_in_note_manager is True
    assert result.submission_started is True
    assert result.detail["backend"] == "applescript-component-event"


def test_publishers_share_one_persistent_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances = []

    class SuccessfulBackend:
        def __init__(self) -> None:
            self.calls = 0
            instances.append(self)

        def publish(self, request: BackendPublishRequest) -> BackendPublishResult:
            request.validate()
            self.calls += 1
            return BackendPublishResult(
                BackendPublishStatus.PUBLISHED,
                "https://creator.xiaohongshu.com/creator/notemanage",
                "confirmed",
                "标题 2026-08-29",
            )

        def close(self) -> None:
            return None

    monkeypatch.setattr(browser, "SafariAppleScriptBackend", SuccessfulBackend)
    session = SafariSession()
    first = SafariPublisher(max_images=18, session=session)
    second = SafariPublisher(max_images=18, session=session)
    note = PublishNote("标题", "正文", (image(tmp_path),))

    asyncio.run(first.publish(note))
    asyncio.run(second.publish(note))

    assert len(instances) == 1
    assert instances[0].calls == 2


def test_async_adapter_classifies_visible_anti_bot_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RejectedBackend:
        def publish(self, _request: BackendPublishRequest) -> BackendPublishResult:
            raise SubmissionRejectedError("操作频繁")

    monkeypatch.setattr(browser, "SafariAppleScriptBackend", RejectedBackend)
    publisher = SafariPublisher(max_images=1)

    with pytest.raises(SafariPublishError) as raised:
        asyncio.run(publisher.publish(PublishNote("标题", "正文", (image(tmp_path),))))

    assert raised.value.submission_started is True
    assert raised.value.code == "XHS_ANTI_BOT"


def test_async_adapter_preflight_and_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ReadOnlyBackend:
        def preflight(self) -> dict[str, object]:
            return {"ok": True, "code": "READY", "view": "upload"}

        def recover_confirmation(
            self,
            title: str,
            *,
            minimum_total: int | None,
        ) -> dict[str, object]:
            return {
                "found": title == "标题" and minimum_total == 4,
                "excerpt": "标题 2026-08-28",
            }

    monkeypatch.setattr(browser, "SafariAppleScriptBackend", ReadOnlyBackend)
    publisher = SafariPublisher(max_images=18)

    assert asyncio.run(publisher.preflight())["code"] == "READY"
    assert asyncio.run(publisher.recover_confirmation("标题", minimum_total=4))["found"] is True


def test_safari_session_uses_one_dedicated_minimized_window() -> None:
    open_source = inspect.getsource(SafariTabSession.open)
    eval_source = inspect.getsource(SafariTabSession.run_javascript)

    assert "activate" not in open_source
    assert "front window" not in open_source
    assert '"-gja", "Safari"' in open_source
    assert "make new document" in open_source
    assert "set miniaturized of targetWindow to true" in open_source
    assert 'oldURL starts with "favorites://" or oldURL is "about:blank"' in open_source
    assert "set visible of targetWindow to false" not in open_source
    assert "first tab of targetWindow" in eval_source
    assert "sessionStorage" not in eval_source


def test_safari_session_quits_only_when_the_application_started_safari() -> None:
    open_source = inspect.getsource(SafariTabSession.open)
    close_source = inspect.getsource(SafariTabSession.close)

    assert "safari_was_running=was_running" in open_source
    assert "if safariWasRunning is false" in close_source
    assert 'tell application "Safari" to quit' in close_source
