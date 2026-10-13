"""Long-lived publication workers with fine-grained sink/account locks."""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from xhs_local.core.contracts import PublishNote
from xhs_local.core.errors import (
    AuthenticationRequired,
    ErrorClass,
    PipelineError,
    RemoteAmbiguous,
    ValidationFailure,
    concise_error,
)
from xhs_local.core.states import WorkState, WorkTopic
from xhs_local.rendering.layout import paginate_text
from xhs_local.rendering.renderer import HtmlPhotoGenerator
from xhs_local.storage.dead_letters import DeadLetterRepository
from xhs_local.storage.records import NewsCandidate, RecordsRepository
from xhs_local.storage.remote_operations import RemoteOperationRepository
from xhs_local.storage.work_items import (
    PublicationLedger,
    PublicationSlot,
    StoredWorkItem,
    WorkItemRepository,
)

PublicationHandler = Callable[[StoredWorkItem], Awaitable[None]]
RetryWake = Callable[[], None]


def _news_caption(headlines: list[str]) -> str:
    """One LLM-written sentence per story, never one per image or a truncated batch body."""
    body = "\n".join(
        headline if headline.endswith(("。", "！", "？", "!", "?")) else headline + "。"
        for headline in headlines
    )
    if len(body.encode("utf-16-le")) // 2 > 1000:
        raise ValidationFailure("news caption exceeds the 1000-character limit; do not truncate")
    return body


class AccountLocks:
    def __init__(self) -> None:
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    def get(self, sink: str, account_id: str) -> asyncio.Lock:
        return self._locks.setdefault((sink, account_id), asyncio.Lock())


class PublisherWorker:
    def __init__(
        self,
        queue: asyncio.Queue[str],
        work_items: WorkItemRepository,
        dead_letters: DeadLetterRepository,
        handlers: Mapping[WorkTopic, PublicationHandler],
        *,
        retry_delays: Mapping[WorkTopic, float] | None = None,
        max_attempts: int = 3,
        retry_wake: RetryWake | None = None,
    ) -> None:
        self.queue = queue
        self.work_items = work_items
        self.dead_letters = dead_letters
        self.handlers = dict(handlers)
        self.retry_delays = dict(retry_delays or {})
        self.max_attempts = max_attempts
        self.retry_wake = retry_wake or (lambda: None)
        self.log = logging.getLogger(__name__)

    async def run(self) -> None:
        while True:
            queued = await self.queue.get()
            work_id = queued[1] if isinstance(queued, tuple) else queued
            try:
                work = await asyncio.to_thread(self.work_items.claim, work_id)
                if work is None:
                    continue
                handler = self.handlers.get(work.topic)
                if handler is None:
                    raise RuntimeError(f"no publication handler for {work.topic}")
                await handler(work)
                current = await asyncio.to_thread(self.work_items.get, work_id)
                if current is not None and current.state is WorkState.RUNNING:
                    await asyncio.to_thread(self.work_items.succeed, work_id)
                elif current is not None and current.state is WorkState.RETRY_WAIT:
                    self.retry_wake()
            except asyncio.CancelledError:
                raise
            except RemoteAmbiguous as error:
                await asyncio.to_thread(
                    self.work_items.reconcile_only,
                    work_id,
                    error_class=error.error_class.value,
                    error_summary=concise_error(error),
                )
            except AuthenticationRequired as error:
                await asyncio.to_thread(
                    self.work_items.wait_for_operator,
                    work_id,
                    error_class=error.error_class.value,
                    error_summary=concise_error(error),
                )
            except PipelineError as error:
                self.log.exception("publication failed", extra={"context": {"work_id": work_id}})
                current = await asyncio.to_thread(self.work_items.get, work_id)
                if current is not None and current.state is WorkState.SUBMITTING:
                    await asyncio.to_thread(
                        self.work_items.reconcile_only,
                        work_id,
                        error_class="REMOTE_AMBIGUOUS",
                        error_code=error.code,
                        error_summary=concise_error(error),
                    )
                elif (
                    error.retryable
                    and current is not None
                    and (
                        error.error_class is ErrorClass.TRANSIENT_NETWORK
                        or current.attempt < self.max_attempts
                    )
                ):
                    await asyncio.to_thread(
                        self.work_items.schedule_retry,
                        work_id,
                        retry_at=datetime.now(UTC)
                        + timedelta(seconds=self.retry_delays.get(current.topic, 10)),
                        error_class=error.error_class.value,
                        error_code=error.code,
                        error_summary=concise_error(error),
                    )
                    self.retry_wake()
                else:
                    terminal = (
                        self.work_items.reject
                        if error.error_class
                        in {ErrorClass.VALIDATION_FAILED, ErrorClass.POLICY_REJECTED}
                        else self.dead_letters.move
                    )
                    await asyncio.to_thread(
                        terminal,
                        work_id,
                        error_class=error.error_class.value,
                        error_code=error.code,
                        error_summary=concise_error(error),
                    )
            except Exception as error:
                self.log.exception("publication failed", extra={"context": {"work_id": work_id}})
                current = await asyncio.to_thread(self.work_items.get, work_id)
                if current is not None and current.state is WorkState.SUBMITTING:
                    await asyncio.to_thread(
                        self.work_items.reconcile_only,
                        work_id,
                        error_class="REMOTE_AMBIGUOUS",
                        error_summary=concise_error(error),
                    )
                elif current is not None and current.attempt < self.max_attempts:
                    await asyncio.to_thread(
                        self.work_items.schedule_retry,
                        work_id,
                        retry_at=datetime.now(UTC)
                        + timedelta(seconds=self.retry_delays.get(current.topic, 10)),
                        error_class="PLUGIN_BUG",
                        error_summary=concise_error(error),
                    )
                    self.retry_wake()
                else:
                    await asyncio.to_thread(
                        self.dead_letters.move,
                        work_id,
                        error_class="PLUGIN_BUG",
                        error_summary=concise_error(error),
                    )
            finally:
                self.queue.task_done()


def _gif_paths(candidate: NewsCandidate, runtime_root: Path) -> list[Path]:
    paths: list[Path] = []
    for attachment in candidate.attachments:
        if attachment.mime_type.lower() != "image/gif":
            continue
        path = attachment.absolute_path(runtime_root)
        try:
            signature = path.read_bytes()[:6]
        except OSError:
            continue
        if signature in {b"GIF87a", b"GIF89a"}:
            paths.append(path)
    return paths


def _materialize_gifs(source_groups: list[list[Path]], directory: Path) -> list[list[Path]]:
    directory.mkdir(parents=True, exist_ok=True)
    materialized: list[list[Path]] = []
    for card_index, sources in enumerate(source_groups, start=1):
        card_paths: list[Path] = []
        for animation_index, source in enumerate(sources, start=1):
            destination = directory / (f"story-{card_index:02d}-motion-{animation_index}.gif")
            shutil.copyfile(source, destination)
            card_paths.append(destination)
        materialized.append(card_paths)
    return materialized


class NewsPublicationService:
    """Behavior-compatible news slot workflow injected into a publisher worker."""

    def __init__(
        self,
        *,
        records: RecordsRepository,
        ledger: PublicationLedger,
        remote_operations: RemoteOperationRepository,
        processor,
        renderer: HtmlPhotoGenerator,
        sink: Any,
        sink_lock: asyncio.Lock,
        runtime_root: Path,
        interval_minutes: float,
        retry_delay_seconds: float = 60,
        capacity: int,
        sink_id: str,
        account_id: str,
        minimum_text_characters: int = 20,
        source_plugins: tuple[str, ...] = (),
        source_presentations: Mapping[str, str] | None = None,
        source_card_templates: Mapping[str, str] | None = None,
        avatar_required_plugins: frozenset[str] = frozenset(),
    ) -> None:
        self.records = records
        self.ledger = ledger
        self.remote_operations = remote_operations
        self.processor = processor
        self.renderer = renderer
        self.sink = sink
        self.sink_lock = sink_lock
        self.runtime_root = runtime_root
        self.interval_minutes = interval_minutes
        self.retry_delay_seconds = float(retry_delay_seconds)
        self.capacity = capacity
        self.sink_id = sink_id
        self.account_id = account_id
        self.minimum_text_characters = minimum_text_characters
        self.source_plugins = tuple(source_plugins)
        self.source_presentations = dict(source_presentations or {})
        self.source_card_templates = dict(source_card_templates or {})
        self.avatar_required_plugins = avatar_required_plugins
        self.log = logging.getLogger(__name__)

    async def reconcile_pending(self) -> bool:
        settled = False
        for operation in await asyncio.to_thread(self.remote_operations.unresolved):
            request = operation.request or {}
            if operation.state != "AMBIGUOUS" or operation.operation != "publish_news_note":
                continue
            if not all(request.get(key) for key in ("record_ids", "slot_start", "slot_end")):
                continue  # Legacy reservations need their original record IDs recovered first.
            async with self.sink_lock:
                current = await asyncio.to_thread(
                    self.remote_operations.get, operation.operation_id
                )
                if current is None or current.state != "AMBIGUOUS":
                    continue
                result = await self.sink.reconcile({**request, "created_at": operation.created_at})
            if result is None:
                continue
            slot = PublicationSlot(request["slot_start"], request["slot_end"])
            if result.ok and result.confirmed_in_note_manager:
                published_at = datetime.fromisoformat(result.detail["published_at"])
                confirmed = await asyncio.to_thread(
                    self.remote_operations.succeed,
                    operation.operation_id,
                    result={"ok": True, "confirmed_in_note_manager": True, **result.detail},
                    now=published_at,
                )
                if not confirmed:
                    continue
                await asyncio.to_thread(
                    self.ledger.mark_records,
                    request["record_ids"],
                    "published",
                    sink=self.sink_id,
                    account_id=self.account_id,
                    now=published_at,
                )
                await asyncio.to_thread(
                    self.ledger.finish,
                    slot,
                    "published",
                    title=request["title"],
                    item_count=len(request["record_ids"]),
                    details=result.detail,
                    now=published_at,
                )
                if request.get("catchup_cutoff") and request.get("source_plugin"):
                    await asyncio.to_thread(
                        self.ledger.discard_unpublished_news_before,
                        datetime.fromisoformat(request["catchup_cutoff"]),
                        sink=self.sink_id,
                        account_id=self.account_id,
                        plugin_id=request["source_plugin"],
                    )
            elif result.detail.get("found") is False:
                rejected = await asyncio.to_thread(
                    self.remote_operations.reject_absent,
                    operation.operation_id,
                    evidence="Dated note history covers the submission; matching note is absent",
                )
                if not rejected:
                    continue
                await asyncio.to_thread(
                    self.ledger.release_records,
                    request["record_ids"],
                    sink=self.sink_id,
                    account_id=self.account_id,
                )
                await asyncio.to_thread(
                    self.ledger.release_rejected_records,
                    request["record_ids"],
                    sink=self.sink_id,
                    account_id=self.account_id,
                )
                await asyncio.to_thread(self.ledger.finish, slot, "failed", details=result.detail)
            else:
                continue
            settled = True
        return settled

    async def __call__(self, work: StoredWorkItem) -> str:
        now = datetime.now(UTC)
        reason = str(work.payload.get("reason") or "")
        source_plugin = work.payload.get("source_plugin")
        if reason == "catchup" and source_plugin not in self.source_plugins:
            raise ValueError("catch-up publication requires one configured source platform")
        requested_plugins = (
            (source_plugin,)
            if isinstance(source_plugin, str) and source_plugin
            else self.source_plugins
        )
        plugin_groups: tuple[str | None, ...] = requested_plugins or (None,)
        window_start = work.payload.get("candidate_window_start")
        window_end = work.payload.get("candidate_window_end")
        if (window_start is None) != (window_end is None):
            raise ValueError("candidate publication window requires both start and end")
        explicit_window = isinstance(window_start, str) and isinstance(window_end, str)
        if explicit_window:
            start = datetime.fromisoformat(window_start.replace("Z", "+00:00"))
            end = datetime.fromisoformat(window_end.replace("Z", "+00:00"))
            if end <= start:
                raise ValueError("candidate publication window end must be after start")
            slot = await asyncio.to_thread(self.ledger.claim_ad_hoc_slot, now)
        else:
            slot = await asyncio.to_thread(
                self.ledger.claim_rolling_slot,
                now,
                interval_minutes=self.interval_minutes,
            )
        if slot is None:
            return "duplicate"
        if not explicit_window:
            start = datetime.fromisoformat(slot.start.replace("Z", "+00:00"))
            end = datetime.fromisoformat(slot.end.replace("Z", "+00:00"))
        fresh: list[NewsCandidate] = []
        reserve: list[NewsCandidate] = []
        for plugin_id in plugin_groups:
            plugin_ids = (plugin_id,) if plugin_id else None
            fresh.extend(
                await asyncio.to_thread(
                    self.records.news_candidates,
                    start,
                    end,
                    limit=max(12, self.capacity),
                    sink=self.sink_id,
                    account_id=self.account_id,
                    minimum_text_characters=self.minimum_text_characters,
                    plugin_ids=plugin_ids,
                    descending=reason.startswith("backlog"),
                )
            )
            if not explicit_window:
                reserve.extend(
                    await asyncio.to_thread(
                        self.records.news_candidates,
                        start - timedelta(hours=24),
                        start,
                        limit=max(8, self.capacity // 2),
                        descending=True,
                        sink=self.sink_id,
                        account_id=self.account_id,
                        minimum_text_characters=self.minimum_text_characters,
                        plugin_ids=plugin_ids,
                    )
                )
        fresh.sort(
            key=lambda candidate: (candidate.occurred_at, candidate.record_id),
            reverse=reason.startswith("backlog"),
        )
        reserve.sort(
            key=lambda candidate: (candidate.occurred_at, candidate.record_id),
            reverse=True,
        )
        candidates: list[NewsCandidate] = []
        seen: set[str] = set()
        for candidate in [*fresh, *reserve]:
            if candidate.record_id not in seen:
                seen.add(candidate.record_id)
                candidates.append(candidate)
        candidates = [
            candidate
            for candidate in candidates
            if candidate.plugin_id not in self.avatar_required_plugins
            or candidate.avatar is not None
        ]
        if candidates:
            compose_options = {}
            if reason in {"startup", "capacity", "backlog", "catchup"}:
                compose_options["fill_capacity"] = True
            if reason == "catchup":
                compose_options["catch_up"] = True
            if reason in {"five_star", "backlog_five_star"}:
                compose_options["five_star_only"] = True
                compose_options["fill_capacity"] = True
            if reason in {"scheduled", "startup", "backlog"}:
                compose_options["scheduled_best_only"] = True
                compose_options["preserve_original_ids"] = frozenset(
                    candidate.record_id
                    for candidate in candidates
                    if self.source_presentations.get(candidate.plugin_id)
                    == "original_with_chinese_translation"
                )
                active_plugins = tuple(sorted({candidate.plugin_id for candidate in candidates}))
                compose_options["platform_publish_counts"] = await asyncio.to_thread(
                    self.records.published_counts_by_plugin,
                    now - timedelta(hours=24),
                    sink=self.sink_id,
                    account_id=self.account_id,
                    plugin_ids=active_plugins,
                )
            if work.payload.get("presentation") == "original_with_chinese_translation":
                compose_options["preserve_original"] = True
            editorial = await self.processor.compose(
                candidates,
                max_items=self.capacity,
                **compose_options,
            )
        else:
            editorial = None
        if editorial is None or not editorial.items:
            if reason in {"five_star", "backlog_five_star"}:
                await asyncio.to_thread(
                    self.ledger.finish,
                    slot,
                    "deferred",
                    details={"evaluated_count": len(candidates)},
                )
                return "deferred"
            if candidates:
                await asyncio.to_thread(
                    self.ledger.mark_records,
                    [
                        record_id
                        for candidate in candidates
                        for record_id in candidate.group_record_ids
                    ],
                    "skipped",
                    sink=self.sink_id,
                    account_id=self.account_id,
                )
            outcome = "filtered" if candidates else "empty"
            await asyncio.to_thread(
                self.ledger.finish,
                slot,
                outcome,
                details={"evaluated_count": len(candidates)},
            )
            return outcome

        # Discard the model's batch body; build captions from the stories actually rendered.
        editorial = replace(editorial, body="")
        by_id = {candidate.record_id: candidate for candidate in candidates}
        cover = editorial.items[0]
        cover_platform = by_id[cover.record_id].plugin_id
        selected_items = tuple(
            item for item in editorial.items if by_id[item.record_id].plugin_id == cover_platform
        )
        if cover.star_rating == 5 and reason != "catchup":
            selected_items = selected_items[:1]
        if selected_items != editorial.items:
            editorial = replace(editorial, items=selected_items, title=cover.headline[:20])
        cards: list[dict[str, Any]] = []
        animations: list[list[Path]] = []
        image_count = 0
        for item in editorial.items:
            candidate = by_id.get(item.record_id)
            if candidate is None or image_count >= self.capacity:
                continue
            video = candidate.plugin_id == "youtube"
            paginated = candidate.plugin_id in {"x", "youtube"}
            pages = (
                await self.renderer.paginate_x_story(
                    item.text,
                    headline=item.headline,
                    attachments=candidate.attachments,
                )
                if candidate.plugin_id == "x"
                else paginate_text(item.text)
                if video
                else [item.text]
            )
            available = max(0, self.capacity - image_count - len(pages))
            gifs = _gif_paths(candidate, self.runtime_root)[:available]
            required = len(pages) + len(gifs)
            if image_count + required > self.capacity:
                if not cards:
                    raise ValidationFailure("complete story exceeds the note image capacity")
                continue
            for page_index, page in enumerate(pages):
                cards.append(
                    {
                        "record_id": item.record_id,
                        "headline": candidate.title if video and candidate.title else item.headline,
                        "text": page,
                        "source_platform": candidate.plugin_id,
                        "story_has_media": bool(candidate.attachments),
                        **(
                            {"story_page": page_index + 1, "story_pages": len(pages)}
                            if paginated
                            else {}
                        ),
                        "source": candidate.source_name,
                        "occurred_at": candidate.occurred_at,
                        "attachments": ()
                        if candidate.plugin_id == "x" and page_index > 0
                        else candidate.attachments,
                        "avatar": candidate.avatar,
                        "template_name": work.payload.get("card_template")
                        or self.source_card_templates.get(candidate.plugin_id),
                    }
                )
                animations.append(gifs if page_index == 0 else [])
            image_count += required
        underfilled_strict_note = reason == "capacity" and image_count < self.capacity
        if underfilled_strict_note:
            await asyncio.to_thread(
                self.ledger.finish,
                slot,
                "deferred",
                details={
                    "evaluated_count": len(candidates),
                    "selected_count": len(cards),
                    "image_count": image_count,
                    "required_image_count": self.capacity,
                },
            )
            return "deferred"
        selected = list({card["record_id"]: by_id[card["record_id"]] for card in cards}.values())
        if len(selected) < len(editorial.items) and any(
            candidate.plugin_id in {"x", "youtube"} for candidate in selected
        ):
            editorial = replace(
                editorial,
                title=editorial.items[0].headline[:20],
            )
        selected_ids = [record_id for item in selected for record_id in item.group_record_ids]
        selected_item_ids = {item.record_id for item in selected}
        editorial = replace(
            editorial,
            body=_news_caption(
                [
                    item.summary or item.headline
                    for item in editorial.items
                    if item.record_id in selected_item_ids
                ]
            ),
        )
        card_paths: list[Path] = []
        animation_dir: Path | None = None
        try:
            if any(animations):
                animation_dir = Path(tempfile.mkdtemp(prefix="xhs-news-motion-"))
                animations = await asyncio.to_thread(_materialize_gifs, animations, animation_dir)
            card_paths = await self.renderer.generate_news_cards(
                cards,
                prefix=f"slot-{slot.start.translate(str.maketrans('', '', '-:.'))}",
            )
            upload_paths = tuple(
                path
                for index, card_path in enumerate(card_paths)
                for path in (card_path, *animations[index])
            )
            authorized = await asyncio.to_thread(
                self.ledger.authorize_publish,
                slot,
                selected_ids,
                title=editorial.title,
                item_count=len(cards),
                sink=self.sink_id,
                account_id=self.account_id,
            )
            if not authorized:
                raise RuntimeError("publication slot fence was already consumed")
            operation = await asyncio.to_thread(
                self.remote_operations.begin,
                work.work_id,
                sink=self.sink_id,
                account_id=self.account_id,
                operation="publish_news_note",
                idempotency_key=f"news:{slot.start}:{slot.end}",
                request={
                    "title": editorial.title,
                    "body": editorial.body,
                    "images": len(upload_paths),
                    "record_ids": selected_ids,
                    "slot_start": slot.start,
                    "slot_end": slot.end,
                    "source_plugin": source_plugin,
                    "catchup_cutoff": end.isoformat()
                    if reason == "catchup" and explicit_window
                    else None,
                },
            )
            if operation is None:
                raise RuntimeError("remote operation fence was already consumed")
            try:
                async with self.sink_lock:
                    result = await self.sink.publish(
                        PublishNote(
                            editorial.title,
                            editorial.body,
                            upload_paths,
                            topics=editorial.tags,
                        )
                    )
                if not result.ok:
                    raise RuntimeError("publication sink returned no positive confirmation")
            except Exception as error:
                rejection_code = getattr(error, "code", None)
                if rejection_code == "XHS_REMOTE_REJECTED":
                    await asyncio.to_thread(
                        self.remote_operations.reject_submission,
                        operation.operation_id,
                        evidence=concise_error(error),
                    )
                    await asyncio.to_thread(
                        self.ledger.mark_records,
                        selected_ids,
                        "skipped",
                        sink=self.sink_id,
                        account_id=self.account_id,
                    )
                    await asyncio.to_thread(
                        self.ledger.finish,
                        slot,
                        "rejected",
                        item_count=len(cards),
                        error=concise_error(error),
                    )
                    return "rejected"
                if rejection_code in {"XHS_DAILY_LIMIT", "XHS_ANTI_BOT"}:
                    if rejection_code == "XHS_DAILY_LIMIT":
                        local_now = now.astimezone(ZoneInfo("Asia/Shanghai"))
                        retry_at = (local_now + timedelta(days=1)).replace(
                            hour=0,
                            minute=5,
                            second=0,
                            microsecond=0,
                        )
                    else:
                        retry_at = now + timedelta(minutes=max(30, self.interval_minutes * 2))
                    await asyncio.to_thread(
                        self.remote_operations.hold_rate_limit,
                        operation.operation_id,
                        retry_at=retry_at,
                        evidence=concise_error(error),
                    )
                    await asyncio.to_thread(
                        self.ledger.release_records,
                        selected_ids,
                        sink=self.sink_id,
                        account_id=self.account_id,
                    )
                    await asyncio.to_thread(
                        self.ledger.finish,
                        slot,
                        "rate-limited",
                        item_count=len(cards),
                        error=concise_error(error),
                    )
                    return "rate_limited"
                if getattr(error, "submission_started", False):
                    await asyncio.to_thread(
                        self.remote_operations.ambiguous,
                        operation.operation_id,
                        error_summary=concise_error(error),
                    )
                    await asyncio.to_thread(
                        self.ledger.mark_records,
                        selected_ids,
                        "failed",
                        sink=self.sink_id,
                        account_id=self.account_id,
                    )
                    await asyncio.to_thread(
                        self.ledger.finish,
                        slot,
                        "publish-failed",
                        item_count=len(cards),
                        error=concise_error(error),
                    )
                    return "ambiguous"
                await asyncio.to_thread(
                    self.remote_operations.not_submitted,
                    operation.operation_id,
                    error_summary=concise_error(error),
                    retry_at=now + timedelta(seconds=self.retry_delay_seconds),
                )
                await asyncio.to_thread(
                    self.ledger.release_records,
                    selected_ids,
                    sink=self.sink_id,
                    account_id=self.account_id,
                )
                await asyncio.to_thread(
                    self.ledger.finish,
                    slot,
                    "failed",
                    item_count=len(cards),
                    error=concise_error(error),
                )
                return "not_submitted"
            remote_saved = await asyncio.to_thread(
                self.remote_operations.succeed,
                operation.operation_id,
                result={
                    "ok": result.ok,
                    "confirmed_in_note_manager": result.confirmed_in_note_manager,
                    **result.detail,
                },
            )
            if not remote_saved:
                raise RuntimeError("publication result could not be persisted")
            await asyncio.to_thread(
                self.ledger.mark_records,
                selected_ids,
                "published",
                sink=self.sink_id,
                account_id=self.account_id,
            )
            if reason == "catchup" and explicit_window:
                # A resumed durable task must retire its own backlog even if its original
                # startup coroutine was interrupted. Never depend on an in-memory waiter.
                await asyncio.to_thread(
                    self.ledger.discard_unpublished_news_before,
                    end,
                    sink=self.sink_id,
                    account_id=self.account_id,
                    plugin_id=source_plugin,
                )
            await asyncio.to_thread(
                self.ledger.finish,
                slot,
                "published",
                title=editorial.title,
                item_count=len(cards),
                details={
                    "image_count": len(upload_paths),
                    "confirmed_in_note_manager": result.confirmed_in_note_manager,
                },
            )
        except Exception as error:
            await asyncio.to_thread(
                self.ledger.finish,
                slot,
                "failed",
                item_count=len(selected),
                error=concise_error(error),
            )
            raise
        finally:
            for path in card_paths:
                if not path.name.startswith("video-"):
                    path.unlink(missing_ok=True)
            if animation_dir is not None:
                await asyncio.to_thread(shutil.rmtree, animation_dir, True)
        return "published"
