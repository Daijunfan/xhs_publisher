"""Publish through the authenticated Apple Safari creator-center session."""

from __future__ import annotations

import base64
import json
import mimetypes
import re
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .errors import (
    SafariAutomationError,
    SubmissionRejectedError,
    SubmissionUncertainError,
)

if sys.platform == "darwin":
    from .macos import SafariTabSession
else:
    from .chromium_session import ChromiumTabSession as SafariTabSession
from .models import BackendPublishRequest, BackendPublishResult, BackendPublishStatus

PUBLISH_URL = (
    "https://creator.xiaohongshu.com/publish/publish?source=official&from=menu&target=image"
)
NOTE_MANAGER_URL = "https://creator.xiaohongshu.com/creator/notemanage"


def reconcile_note_history(
    text: str, *, title: str, body: str, created_at: str, total: int, now: datetime | None = None
) -> dict[str, Any]:
    """Require a dated exact title/body match, or coverage of the submission time."""
    since = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    cutoff = since.astimezone(ZoneInfo("Asia/Shanghai")).replace(second=0, microsecond=0)
    parts = re.split(r"\n(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\n", text)

    def normalize(value: str) -> str:
        return re.sub(r"[\W_]+", "", value).casefold()

    dates = []
    for index in range(1, len(parts), 2):
        stamp = datetime.strptime(parts[index], "%Y-%m-%d %H:%M").replace(tzinfo=cutoff.tzinfo)
        dates.append(stamp)
        lines = [line.strip() for line in parts[index - 1].splitlines() if line.strip()]
        snippet = lines[-1] if lines else ""
        title_match = bool(title) and normalize(snippet) == normalize(title)
        body_key = normalize(body)[:24]
        body_match = len(body_key) >= 8 and normalize(snippet).startswith(body_key)
        if stamp >= cutoff and (title_match or body_match):
            return {
                "found": True,
                "published_at": stamp.isoformat(),
                "excerpt": snippet,
                "total": total,
            }
    settled = (now or datetime.now(UTC)) - since >= timedelta(minutes=2)
    covered = total > 0 and (
        dates == sorted(dates, reverse=True) and dates and min(dates) <= cutoff
    )
    return {"found": False if settled and covered else None, "total": total}


class SafariAppleScriptBackend:
    """Synchronous Safari DOM backend imported from the proven standalone publisher."""

    def __init__(self) -> None:
        self._session: SafariTabSession | None = None

    def preflight(self, timeout_seconds: float = 45.0) -> dict[str, Any]:
        session = self._ensure_session(PUBLISH_URL)
        state = self._ensure_publish_page(timeout_seconds)
        return {
            "ok": True,
            "code": "READY",
            "window_id": session.window_id,
            "view": state["view"],
        }

    def publish(self, request: BackendPublishRequest) -> BackendPublishResult:
        request.validate()
        self._ensure_session(NOTE_MANAGER_URL)
        baseline = self._read_note_baseline(request.timeout_seconds)
        state = self._ensure_publish_page(request.timeout_seconds)
        if state["view"] == "editor":
            self._validate_reusable_editor(state, request)
        else:
            self._upload_images(request.image_paths)
            self._wait_for(
                lambda current: (
                    current["view"] == "editor"
                    and current["media_count"] == len(request.image_paths)
                    and current["uploading_count"] == 0
                ),
                timeout=request.timeout_seconds,
                purpose="completed image uploads",
            )

        self._fill_note(request.title, request.effective_body)
        state = self._wait_for(
            lambda current: (
                current["view"] == "editor"
                and current["title"] == request.title
                and current["body"] == request.effective_body
                and current["media_count"] == len(request.image_paths)
                and current["uploading_count"] == 0
                and not current["submit_disabled"]
            ),
            timeout=request.timeout_seconds,
            purpose="ready-to-publish form",
        )
        self._submit_note()
        try:
            result = self._wait_for_submission(request.timeout_seconds, state["url"])
        except SubmissionUncertainError:
            result = BackendPublishResult(
                status=BackendPublishStatus.PUBLISHED,
                page_url=state["url"],
                message="submission required note-manager recovery",
                excerpt="",
            )
        confirmation = self._confirm_note(
            request.title,
            minimum_total=baseline + 1,
            timeout=request.timeout_seconds,
        )
        return BackendPublishResult(
            status=result.status,
            page_url=result.page_url,
            message=result.message,
            excerpt=confirmation["excerpt"],
        )

    def recover_confirmation(
        self,
        title: str,
        *,
        minimum_total: int | None,
        timeout_seconds: float = 45.0,
    ) -> dict[str, Any]:
        self._ensure_session(NOTE_MANAGER_URL)
        return self._confirm_note(
            title,
            minimum_total=minimum_total,
            timeout=timeout_seconds,
            navigate=False,
        )

    def close(self) -> None:
        if self._session is None:
            return
        session, self._session = self._session, None
        session.close()

    def probe_submission(self, *, title: str, body: str, created_at: str) -> dict[str, Any]:
        self._ensure_session(NOTE_MANAGER_URL)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            state = self._read_manager("", minimum_total=None)
            if state.get("loaded") and state.get("total", 0) > 0:
                text = json.loads(self._run_javascript("JSON.stringify(document.body.innerText)"))
                return reconcile_note_history(
                    text, title=title, body=body, created_at=created_at, total=state["total"]
                )
            time.sleep(0.5)
        raise SafariAutomationError("note history unavailable; keep the submission unconfirmed")

    def _ensure_session(self, url: str) -> SafariTabSession:
        if self._session is None:
            self._session = SafariTabSession.open(url)
        else:
            self._session.navigate(url)
        return self._session

    def _read_note_baseline(self, timeout: float) -> int:
        baseline = self._wait_for_manager(timeout)["total"]
        self._navigate(PUBLISH_URL)
        return int(baseline)

    def _ensure_publish_page(self, timeout: float) -> dict[str, Any]:
        return self._wait_for(
            lambda current: current["view"] in {"upload", "editor"},
            timeout=timeout,
            purpose="Xiaohongshu image publishing page",
        )

    @staticmethod
    def _validate_reusable_editor(state: dict[str, Any], request: BackendPublishRequest) -> None:
        has_existing_text = bool(state["title"] or state["body"])
        same_content = state["title"] == request.title and state["body"] == request.effective_body
        same_media_count = state["media_count"] == len(request.image_paths)
        if has_existing_text and not (same_content and same_media_count):
            raise SafariAutomationError(
                "Safari contains a different unfinished draft; refusing to overwrite it"
            )
        if state["media_count"] and not same_media_count:
            raise SafariAutomationError(
                "Safari contains a different image count; refusing to add duplicate media"
            )

    def _upload_images(self, image_paths: tuple[Path, ...]) -> None:
        images = []
        for path in image_paths:
            images.append(
                {
                    "name": path.name,
                    "type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    "base64": base64.b64encode(path.read_bytes()).decode("ascii"),
                }
            )
        payload = json.dumps(images, ensure_ascii=True)
        script = rf"""
(() => {{
    const input = Array.from(document.querySelectorAll('input[type=file]'))
        .find(element => element.accept.includes('.png'));
    if (!input) throw new Error('image file input not found');
    const transfer = new DataTransfer();
    for (const image of {payload}) {{
        const binary = atob(image.base64);
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) {{
            bytes[index] = binary.charCodeAt(index);
        }}
        transfer.items.add(new File([bytes], image.name, {{ type: image.type }}));
    }}
    input.files = transfer.files;
    input.dispatchEvent(new Event('input', {{ bubbles: true, composed: true }}));
    input.dispatchEvent(new Event('change', {{ bubbles: true, composed: true }}));
    return JSON.stringify({{ selected: transfer.files.length }});
}})()
"""
        result = json.loads(self._run_javascript(script))
        if result != {"selected": len(image_paths)}:
            raise SafariAutomationError("Safari did not accept all selected images")

    def _fill_note(self, title: str, body: str) -> None:
        if self._session is not None and hasattr(self._session, "fill_note"):
            result = self._session.fill_note(title, body)
            if result != {"title": title, "body": body}:
                raise SafariAutomationError("Chromium did not retain the requested title and body")
            return
        title_json = json.dumps(title, ensure_ascii=True)
        body_json = json.dumps(body, ensure_ascii=True)
        script = f"""
(() => {{
    const title = document.querySelector('input[placeholder*="标题"]');
    const editor = document.querySelector('[contenteditable=true].ProseMirror');
    if (!title || !editor) throw new Error('note editor fields not found');
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setValue.call(title, {title_json});
    title.dispatchEvent(new InputEvent('input', {{
        bubbles: true, inputType: 'insertText', data: {title_json}
    }}));
    title.dispatchEvent(new Event('change', {{ bubbles: true }}));
    editor.focus();
    const selection = getSelection();
    const range = document.createRange();
    range.selectNodeContents(editor);
    selection.removeAllRanges();
    selection.addRange(range);
    document.execCommand('insertText', false, {body_json});
    editor.dispatchEvent(new Event('change', {{ bubbles: true }}));
    editor.blur();
    title.blur();
    const page = document.querySelector('.publish-page');
    if (page) page.scrollTop = page.scrollHeight;
    return JSON.stringify({{ title: title.value, body: editor.innerText.trim() }});
}})()
"""
        result = json.loads(self._run_javascript(script))
        result = json.loads(self._run_javascript(script))
        if result != {"title": title, "body": body}:
            raise SafariAutomationError("Safari did not retain the requested title and body")

    def _read_state(self) -> dict[str, Any]:
        script = r"""
(() => {
    const title = document.querySelector('input[placeholder*="标题"]');
    const editor = document.querySelector('[contenteditable=true].ProseMirror');
    const imageInput = Array.from(document.querySelectorAll('input[type=file]'))
        .find(element => element.accept.includes('.png'));
    const publishHost = document.querySelector('xhs-publish-btn');
    const statusText = document.querySelector('.publish-page-content-media .status')
        ?.innerText.trim() || '';
    const mediaMatch = statusText.match(/^(\d+)\s*\/\s*18$/);
    const text = document.body?.innerText || '';
    let view = 'loading';
    if (title && editor) view = 'editor';
    else if (imageInput) view = 'upload';
    return JSON.stringify({
        view, url: location.href,
        title: title?.value.trim() || '',
        body: editor?.innerText.trim() || '',
        media_count: mediaMatch ? Number(mediaMatch[1]) : 0,
        uploading_count: document.querySelectorAll('.mask.uploading, .progress-container').length,
        submit_disabled: publishHost?.getAttribute('submit-disabled') !== 'false',
        submit_loading: publishHost?.getAttribute('submit-loading') === 'true',
        page_text: text.slice(-2500)
    });
})()
"""
        return json.loads(self._run_javascript(script))

    def _wait_for(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        *,
        timeout: float,
        purpose: str,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = self._read_state()
            if predicate(last_state):
                return last_state
            time.sleep(0.5)
        raise SafariAutomationError(f"timed out waiting for {purpose}: {last_state}")

    def _submit_note(self) -> None:
        script = """
(() => {
    const publishHost = document.querySelector('xhs-publish-btn');
    if (!publishHost) throw new Error('publish component not found');
    if (publishHost.getAttribute('submit-disabled') !== 'false') {
        throw new Error('publish component is disabled');
    }
    if (publishHost.getAttribute('submit-loading') === 'true') {
        throw new Error('publish component is already submitting');
    }
    publishHost.dispatchEvent(new CustomEvent('publish', {
        bubbles: true, composed: true
    }));
    return JSON.stringify({ submitted: true });
})()
"""
        result = json.loads(self._run_javascript(script))
        if result != {"submitted": True}:
            raise SafariAutomationError("Safari did not dispatch the publish event")

    def _wait_for_submission(self, timeout: float, previous_url: str) -> BackendPublishResult:
        deadline = time.monotonic() + timeout
        last_state: dict[str, Any] = {}
        rejection_markers = (
            "发布失败",
            "发布次数已达上限",
            "今日发布次数已达上限",
            "操作频繁",
        )
        while time.monotonic() < deadline:
            last_state = self._read_state()
            page_text = last_state["page_text"]
            if any(marker in page_text for marker in rejection_markers):
                raise SubmissionRejectedError(page_text)
            if "发布成功" in page_text:
                return BackendPublishResult(
                    BackendPublishStatus.PUBLISHED,
                    last_state["url"],
                    "Xiaohongshu displayed a publish-success confirmation",
                    "",
                )
            if last_state["url"] != previous_url and "/publish/publish" not in last_state["url"]:
                return BackendPublishResult(
                    BackendPublishStatus.PUBLISHED,
                    last_state["url"],
                    "Xiaohongshu navigated away from the publishing form",
                    "",
                )
            time.sleep(0.5)
        raise SubmissionUncertainError(
            "the publish event was dispatched, but Safari showed no verifiable outcome"
        )

    def _confirm_note(
        self,
        title: str,
        *,
        minimum_total: int | None,
        timeout: float,
        navigate: bool = True,
    ) -> dict[str, Any]:
        if navigate:
            self._navigate(NOTE_MANAGER_URL)
        self._wait_for_manager(timeout)
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last = self._read_manager(title, minimum_total=minimum_total)
            if last["found"]:
                return last
            time.sleep(1)
        if (
            minimum_total is not None
            and last.get("loaded")
            and isinstance(last.get("total"), int)
            and last["total"] < minimum_total
        ):
            raise SubmissionRejectedError("note manager total did not increase after submission")
        raise SubmissionUncertainError(
            f"published note did not appear in note manager: {title!r}; last={last}"
        )

    def _wait_for_manager(self, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self._read_manager("", minimum_total=None)
            if state["loaded"]:
                return state
            time.sleep(0.5)
        raise SafariAutomationError("timed out waiting for note manager")

    def _read_manager(self, title: str, *, minimum_total: int | None) -> dict[str, Any]:
        command = json.dumps(
            {"title": title, "minimumTotal": minimum_total},
            ensure_ascii=True,
        )
        script = rf"""
(() => {{
    const command = {command};
    const text = (document.body?.innerText || '').replace(/\s+/g, ' ');
    const totalMatch = text.match(/全部\s*(\d+)/);
    const total = totalMatch ? Number(totalMatch[1]) : null;
    const hasRenderedNote = /\d{{4}}-\d{{2}}-\d{{2}}\s+\d{{2}}:\d{{2}}/.test(text);
    let count = 0;
    let index = -1;
    if (command.title) {{
        let cursor = 0;
        while ((cursor = text.indexOf(command.title, cursor)) !== -1) {{
            if (index === -1) index = cursor;
            count += 1;
            cursor += Math.max(1, command.title.length);
        }}
    }}
    const normalize = value => String(value || '').toLowerCase()
        .replace(/[\s\p{{P}}\p{{S}}]+/gu, '');
    const target = normalize(command.title);
    const targetGrams = [...Array(Math.max(0, target.length - 1))]
        .map((_, index) => target.slice(index, index + 2));
    const snippets = [...document.querySelectorAll('a,div,span,p')]
        .map(node => (node.innerText || '').trim())
        .filter(value => value && value.length <= 120 && !value.includes('\n'));
    let bestScore = 0;
    let matchedTitle = '';
    for (const snippet of snippets) {{
        const candidate = normalize(snippet);
        if (!target || !candidate.includes(target.slice(0, Math.min(2, target.length)))) continue;
        const candidateGrams = new Set(
            [...Array(Math.max(0, candidate.length - 1))]
                .map((_, gramIndex) => candidate.slice(gramIndex, gramIndex + 2))
        );
        const score = targetGrams.length
            ? targetGrams.filter(gram => candidateGrams.has(gram)).length / targetGrams.length
            : Number(candidate === target);
        if (score > bestScore) {{ bestScore = score; matchedTitle = snippet; }}
    }}
    const titleProof = command.title ? count >= 1 || bestScore >= .45 : true;
    const totalProof = command.minimumTotal === null
        || (total !== null && total >= command.minimumTotal);
    const countGrowth = command.minimumTotal !== null && totalProof;
    return JSON.stringify({{
        loaded: total !== null && (
            total > 0 ? hasRenderedNote : /暂无笔记|还没有发布/.test(text)
        ),
        found: totalProof && (titleProof || countGrowth),
        count, total, bestScore, matchedTitle,
        excerpt: index === -1 ? matchedTitle : text.slice(index, index + 100)
    }});
}})()
"""
        return json.loads(self._run_javascript(script))

    def _navigate(self, url: str) -> None:
        self._run_javascript(f"location.href={json.dumps(url)}; 'navigating'")

    def _run_javascript(self, source: str) -> str:
        if self._session is None:
            raise SafariAutomationError("Safari automation session is not open")
        return self._session.run_javascript(source)
