from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from PIL import Image

from xhs_local.core.contracts import (
    AttachmentInput,
    CollectBatch,
    Editorial,
    EditorialItem,
    PublishNote,
    PublishResult,
    SourceRecord,
)
from xhs_local.core.errors import ValidationFailure
from xhs_local.core.identifiers import stable_record_id
from xhs_local.core.states import WorkState, WorkTopic
from xhs_local.pipeline.publisher import NewsPublicationService, _news_caption
from xhs_local.rendering.layout import paginate_text
from xhs_local.storage.database import Database
from xhs_local.storage.records import NewsCandidate, RecordsRepository
from xhs_local.storage.remote_operations import RemoteOperationRepository
from xhs_local.storage.schema import migrate
from xhs_local.storage.work_items import PublicationLedger, WorkItemRepository


@dataclass(frozen=True, slots=True)
class NewsPool:
    candidate_ids: tuple[str, ...]
    record_ids_by_candidate: dict[str, tuple[str, ...]]
    all_record_ids: tuple[str, ...]
    gif_bytes: bytes


def test_news_caption_summarizes_each_story_within_the_platform_limit():
    headlines = [f"第{index}项技术发布重要进展" for index in range(18)]
    body = _news_caption(headlines)
    assert body.splitlines() == [headline + "。" for headline in headlines]
    assert len(body) < 1000
    assert (
        _news_caption(["模型性能翻倍。", "开源工具正式发布"])
        == "模型性能翻倍。\n开源工具正式发布。"
    )
    assert len(_news_caption(["字" * 999])) == 1000
    with pytest.raises(ValidationFailure, match="do not truncate"):
        _news_caption(["字" * 1000])
    with pytest.raises(ValidationFailure, match="1000"):
        _news_caption(["🚀" * 500])


class FakeProcessor:
    def __init__(self, *, select: bool = True) -> None:
        self.select = select
        self.candidates: list[NewsCandidate] = []
        self.max_items: int | None = None
        self.preserve_original = False
        self.preserve_original_ids: frozenset[str] = frozenset()
        self.fill_capacity = False
        self.five_star_only = False
        self.scheduled_best_only = False
        self.platform_publish_counts: dict[str, int] = {}
        self.output_items: tuple[EditorialItem, ...] = ()

    async def compose(
        self,
        candidates: list[NewsCandidate],
        *,
        max_items: int,
        fill_capacity: bool = False,
        preserve_original: bool = False,
        preserve_original_ids: frozenset[str] = frozenset(),
        five_star_only: bool = False,
        scheduled_best_only: bool = False,
        catch_up: bool = False,
        platform_publish_counts: dict[str, int] | None = None,
    ) -> Editorial:
        self.candidates = list(candidates)
        self.max_items = max_items
        self.preserve_original = preserve_original
        self.preserve_original_ids = preserve_original_ids
        self.fill_capacity = fill_capacity
        self.five_star_only = five_star_only
        self.scheduled_best_only = scheduled_best_only
        self.catch_up = catch_up
        self.platform_publish_counts = dict(platform_publish_counts or {})
        if not self.select:
            return Editorial("", "", (), ())
        selected = candidates[:max_items]
        if scheduled_best_only and selected:
            selected = [item for item in selected if item.plugin_id == selected[0].plugin_id]
        self.output_items = tuple(
            EditorialItem(
                record_id=candidate.record_id,
                headline=f"新闻 {index}",
                text=f"经过编辑的科技新闻正文 {index}",
                star_rating=4,
            )
            for index, candidate in enumerate(selected, start=1)
        )
        return Editorial(
            title="科技快讯",
            body="本时段值得关注的科技产品与研发动态摘要。",
            tags=("科技", "研发"),
            items=self.output_items,
        )


class FakeNewsRenderer:
    def __init__(self, root: Path, *, failure: BaseException | None = None) -> None:
        self.root = root
        self.failure = failure
        self.cards: list[dict] = []
        self.paths: list[Path] = []

    async def paginate_x_story(self, text, *, headline, attachments=()):
        return paginate_text(text, first_page_limit=180 if attachments else None)

    async def generate_news_cards(self, cards, *, prefix: str) -> list[Path]:
        if self.failure is not None:
            raise self.failure
        self.cards = list(cards)
        self.root.mkdir(parents=True, exist_ok=True)
        self.paths = []
        for index, _card in enumerate(cards, start=1):
            path = self.root / f"{prefix}-card-{index}.png"
            Image.new("RGB", (80, 80), "#e8ddff").save(path)
            self.paths.append(path)
        return list(self.paths)


class SinkFailure(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        submission_started: bool,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.submission_started = submission_started
        self.code = code


class FakeNewsSink:
    def __init__(self, *, failure: BaseException | None = None) -> None:
        self.failure = failure
        self.notes: list[PublishNote] = []
        self.image_names: list[str] = []
        self.image_bytes: list[bytes] = []

    async def publish(self, note: PublishNote) -> PublishResult:
        self.notes.append(note)
        self.image_names = [path.name for path in note.images]
        self.image_bytes = [path.read_bytes() for path in note.images]
        if self.failure is not None:
            raise self.failure
        return PublishResult(ok=True, confirmed_in_note_manager=True)


def _record(
    external_id: str,
    occurred_at: datetime,
    *,
    source_name: str,
    group_id: str | None = None,
    text: str | None = None,
    attachment: bytes | None = None,
) -> SourceRecord:
    return SourceRecord(
        record_id=stable_record_id("telegram-main", "telegram-target", external_id),
        source_id="telegram-main",
        target_id="telegram-target",
        plugin_id="telegram",
        external_id=external_id,
        content_type="tech_news",
        occurred_at=occurred_at,
        observed_at=occurred_at,
        text=(
            f"Detailed technology report {external_id} with concrete useful information."
            if text is None
            else text
        ),
        source_name=source_name,
        group_id=group_id,
        attachments=(
            ()
            if attachment is None
            else (AttachmentInput("image/gif", "motion.gif", attachment, 640, 480),)
        ),
    )


def _insert_pool(records: RecordsRepository, now: datetime) -> NewsPool:
    gif_bytes = b"GIF89a-e2e-animation"
    album_caption = _record(
        "100",
        now - timedelta(minutes=10),
        source_name="fresh-album",
        group_id="album-one",
    )
    album_gif = _record(
        "101",
        now - timedelta(minutes=9, seconds=59),
        source_name="fresh-album",
        group_id="album-one",
        text="",
        attachment=gif_bytes,
    )
    fresh = _record("102", now - timedelta(minutes=8), source_name="fresh-standalone")
    reserves = tuple(
        _record(
            str(200 + index),
            now - timedelta(minutes=16 + index),
            source_name=f"reserve-{index + 1}",
        )
        for index in range(6)
    )
    too_old = _record("999", now - timedelta(hours=25), source_name="too-old")
    for item in (album_caption, album_gif, fresh, *reserves, too_old):
        records.upsert(item)

    album_id = stable_record_id("telegram-main", "telegram-target", "group:album-one")
    candidate_ids = (album_id, fresh.record_id, *(item.record_id for item in reserves))
    mapping = {
        album_id: (album_caption.record_id, album_gif.record_id),
        fresh.record_id: (fresh.record_id,),
        **{item.record_id: (item.record_id,) for item in reserves},
    }
    return NewsPool(
        candidate_ids=candidate_ids,
        record_ids_by_candidate=mapping,
        all_record_ids=tuple(
            record_id for candidate_id in candidate_ids for record_id in mapping[candidate_id]
        ),
        gif_bytes=gif_bytes,
    )


def _service(
    *,
    records: RecordsRepository,
    database: Database,
    runtime_root: Path,
    processor: FakeProcessor,
    renderer: FakeNewsRenderer,
    sink: FakeNewsSink,
    capacity: int,
    source_presentations: dict[str, str] | None = None,
    source_card_templates: dict[str, str] | None = None,
    source_plugins: tuple[str, ...] = ("telegram", "x"),
) -> NewsPublicationService:
    return NewsPublicationService(
        records=records,
        ledger=PublicationLedger(database),
        remote_operations=RemoteOperationRepository(database),
        processor=processor,
        renderer=renderer,
        sink=sink,
        sink_lock=asyncio.Lock(),
        runtime_root=runtime_root,
        interval_minutes=15,
        capacity=capacity,
        sink_id="xiaohongshu",
        account_id="main",
        source_presentations=source_presentations,
        source_card_templates=source_card_templates,
        source_plugins=source_plugins,
    )


def _claimed_work(database: Database, *, payload: dict | None = None):
    work_items = WorkItemRepository(database)
    work_id = work_items.create(WorkTopic.NEWS_PUBLISH, payload=payload)
    work = work_items.claim(work_id)
    assert work is not None
    return work_items, work


@pytest.mark.parametrize("remote_result", ["published", "absent", "unknown", "offline"])
def test_uncertain_submission_is_reconciled_without_resubmitting(tmp_path, remote_result):
    with Database(tmp_path / "app.sqlite3") as database:
        migrate(database)
        records = RecordsRepository(database, tmp_path)
        record = _record("reconcile", datetime.now(UTC) - timedelta(minutes=5), source_name="test")
        records.upsert(record)
        works, work = _claimed_work(database, payload={"reason": "scheduled"})
        ledger = PublicationLedger(database)
        slot = ledger.claim_ad_hoc_slot(datetime.now(UTC))
        assert ledger.authorize_publish(
            slot,
            [record.record_id],
            title="具体模型升级",
            item_count=1,
            sink="xiaohongshu",
            account_id="main",
        )
        operations = RemoteOperationRepository(database)
        operation = operations.begin(
            work.work_id,
            sink="xiaohongshu",
            account_id="main",
            operation="publish_news_note",
            idempotency_key="recovery-test",
            request={
                "title": "具体模型升级",
                "body": "模型性能有具体升级。",
                "images": 1,
                "record_ids": [record.record_id],
                "slot_start": slot.start,
                "slot_end": slot.end,
            },
        )
        operations.ambiguous(operation.operation_id, error_summary="connection lost after submit")

        class RecoveringSink(FakeNewsSink):
            async def reconcile(self, request):
                assert request["record_ids"] == [record.record_id]
                if remote_result == "offline":
                    raise ConnectionError("offline")
                if remote_result == "unknown":
                    return None
                found = remote_result == "published"
                return PublishResult(
                    found,
                    confirmed_in_note_manager=found,
                    detail={
                        "found": found,
                        "published_at": datetime.now(UTC).isoformat(),
                    },
                )

        sink = RecoveringSink()
        service = _service(
            records=records,
            database=database,
            runtime_root=tmp_path,
            processor=FakeProcessor(),
            renderer=FakeNewsRenderer(tmp_path / "generated"),
            sink=sink,
            capacity=18,
        )
        if remote_result == "offline":
            with pytest.raises(ConnectionError):
                asyncio.run(service.reconcile_pending())
        else:
            assert asyncio.run(service.reconcile_pending()) is (
                remote_result in {"published", "absent"}
            )
        assert sink.notes == []  # Reconciliation is read-only on Xiaohongshu.
        assert (
            operations.get(operation.operation_id).state
            == {
                "published": "SUCCEEDED",
                "absent": "REJECTED",
                "unknown": "AMBIGUOUS",
                "offline": "AMBIGUOUS",
            }[remote_result]
        )
        with database.locked() as connection:
            marks = connection.execute("SELECT status FROM publication_marks").fetchall()
            assert [row[0] for row in marks] == (
                []
                if remote_result == "absent"
                else ["published" if remote_result == "published" else "publishing"]
            )








@pytest.mark.parametrize("featured", ["telegram", "x", "youtube"])
@pytest.mark.parametrize("five_star", [True, False])
def test_three_platforms_are_separate_and_five_star_is_standalone(tmp_path, featured, five_star):
    database = Database(tmp_path / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, tmp_path)
        platforms = ("telegram", "x", "youtube")
        for index, platform in enumerate(platforms):
            for offset in range(2):
                source = _record(
                    str(9000 + index * 10 + offset),
                    datetime.now(UTC) - timedelta(minutes=1),
                    source_name=platform,
                )
                records.upsert(replace(source, plugin_id=platform))

        class MixedProcessor(FakeProcessor):
            async def compose(self, candidates, **kwargs):
                await super().compose(candidates, **kwargs)
                ordered = sorted(candidates, key=lambda item: item.plugin_id != featured)
                self.output_items = tuple(
                    EditorialItem(
                        item.record_id,
                        "具体技术更新",
                        "完整的技术内容。",
                        5 if five_star and index == 0 else 4,
                    )
                    for index, item in enumerate(ordered)
                )
                return Editorial("具体技术更新", "具体技术事实。", ("科技",), self.output_items)

        _works, work = _claimed_work(database, payload={"reason": "scheduled"})
        renderer, sink = FakeNewsRenderer(tmp_path / "generated"), FakeNewsSink()
        service = _service(
            records=records,
            database=database,
            runtime_root=tmp_path,
            processor=MixedProcessor(),
            renderer=renderer,
            sink=sink,
            capacity=18,
            source_plugins=platforms,
        )
        assert asyncio.run(service(work)) == "published"
        assert {card["source_platform"] for card in renderer.cards} == {featured}
        assert sink.notes[0].body.splitlines() == ["具体技术更新。"] * (1 if five_star else 2)
        assert sink.notes[0].allow_empty_text is False
        assert sink.notes[0].topics == ("科技",)
        assert len(renderer.cards) == (1 if five_star else 2)
        with database.locked() as connection:
            marks = connection.execute("SELECT count(*) FROM publication_marks").fetchone()[0]
        assert marks == (1 if five_star else 2)  # Unselected sources/news remain available.
    finally:
        database.close()


@pytest.mark.parametrize("platform", ["telegram", "x", "youtube"])
def test_catchup_fills_one_platform_and_only_retires_its_old_remainder(tmp_path, platform):
    with Database(tmp_path / "app.sqlite3") as database:
        migrate(database)
        records = RecordsRepository(database, tmp_path)
        now = datetime.now(UTC)
        for source_index, source in enumerate(("telegram", "x", "youtube")):
            for index in range(20):
                records.upsert(
                    replace(
                        _record(
                            str(20000 + source_index * 100 + index),
                            now - timedelta(minutes=1),
                            source_name=source,
                        ),
                        plugin_id=source,
                    )
                )
        fresh = replace(
            _record("20999", now + timedelta(minutes=1), source_name=platform), plugin_id=platform
        )
        records.upsert(fresh)

        class CatchupProcessor(FakeProcessor):
            async def compose(self, candidates, **kwargs):
                assert kwargs["catch_up"] and kwargs["fill_capacity"]
                editorial = await super().compose(candidates, **kwargs)
                return replace(
                    editorial,
                    items=tuple(
                        replace(item, star_rating=5 if index < 2 else 4)
                        for index, item in enumerate(editorial.items)
                    ),
                )

        _, work = _claimed_work(
            database,
            payload={
                "reason": "catchup",
                "source_plugin": platform,
                "candidate_window_start": (now - timedelta(hours=1)).isoformat(),
                "candidate_window_end": now.isoformat(),
            },
        )
        renderer, sink = FakeNewsRenderer(tmp_path / "generated"), FakeNewsSink()
        service = _service(
            records=records,
            database=database,
            runtime_root=tmp_path,
            processor=CatchupProcessor(),
            renderer=renderer,
            sink=sink,
            capacity=18,
            source_plugins=("telegram", "x", "youtube"),
        )
        assert asyncio.run(service(work)) == "published"
        assert len(sink.notes) == 1 and len(sink.notes[0].images) == 18
        assert sink.notes[0].body.splitlines() == [f"新闻 {index}。" for index in range(1, 19)]
        assert sink.notes[0].allow_empty_text is False
        assert {card["source_platform"] for card in renderer.cards} == {platform}
        assert (
            PublicationLedger(database).discard_unpublished_news_before(
                now,
                sink="xiaohongshu",
                account_id="main",
                plugin_id=platform,
            )
            == 0  # The durable publication itself already retired this platform's remainder.
        )
        with database.locked() as connection:
            assert connection.execute("SELECT count(*) FROM publication_marks").fetchone()[0] == 20
            assert (
                connection.execute(
                    "SELECT count(*) FROM publication_marks WHERE record_id=?", (fresh.record_id,)
                ).fetchone()[0]
                == 0
            )
            assert {
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT plugin_id FROM records JOIN publication_marks USING(record_id)"
                )
            } == {platform}


@pytest.mark.parametrize("with_media", [False, True])
@pytest.mark.parametrize("five_star", [False, True])
@pytest.mark.parametrize("room_for_next", [False, True])
def test_x_long_story_pages_stay_together_and_are_marked_once(
    tmp_path, with_media, five_star, room_for_next
):
    text = "原文：\n" + "保留长文的技术观点、数字和方法，不缩小文字塞进一页。\n\n" * 30
    text += "背景概述：\n理解这项技术需要的简要背景。"
    buffer = io.BytesIO()
    Image.new("RGB", (160, 90), "#e8ddff").save(buffer, format="PNG")
    image = AttachmentInput("image/png", "avatar.png", buffer.getvalue())
    pages = paginate_text(text, first_page_limit=180 if with_media else None)
    with Database(tmp_path / "app.sqlite3") as database:
        migrate(database)
        records = RecordsRepository(database, tmp_path)
        now = datetime.now(UTC)
        for index in range(2):
            records.upsert(
                replace(
                    _record(
                        str(9900 + index),
                        now - timedelta(minutes=2 - index),
                        source_name="Phoenix Yin",
                    ),
                    plugin_id="x",
                    source_name="Phoenix Yin @Phoenixyin13",
                    text=text
                    if index == 0
                    else "另一条有价值的技术新闻，介绍了具体的模型推理优化方法与测试结果。",
                    attachments=(image, replace(image, file_name="photo.png"))
                    if with_media
                    else (image,),
                    payload={"avatar_attachment_index": 0},
                )
            )

        class LongPostProcessor(FakeProcessor):
            async def compose(self, candidates, **kwargs):
                await super().compose(candidates, **kwargs)
                items = tuple(
                    EditorialItem(
                        candidate.record_id,
                        "长文技术解析",
                        candidate.text,
                        5 if five_star and index == 0 else 4,
                        summary=f"第{index + 1}条新闻的一句话核心总结。",
                    )
                    for index, candidate in enumerate(candidates)
                )
                return Editorial("长文技术解析", "技术观点", ("技术",), items)

        renderer, sink = FakeNewsRenderer(tmp_path / "generated"), FakeNewsSink()
        _, work = _claimed_work(database, payload={"reason": "scheduled"})
        processor = LongPostProcessor()
        service = _service(
            records=records,
            database=database,
            runtime_root=tmp_path,
            processor=processor,
            renderer=renderer,
            sink=sink,
            capacity=18 if room_for_next else len(pages),
            source_card_templates={"x": "x_post.html"},
        )
        assert asyncio.run(service(work)) == "published"
        first_id = processor.candidates[0].record_id
        first_cards = [card for card in renderer.cards if card["record_id"] == first_id]
        assert "".join(card["text"] for card in first_cards) == text
        assert [card["story_page"] for card in first_cards] == list(range(1, len(pages) + 1))
        assert all(card["story_pages"] == len(pages) for card in first_cards)
        assert all(card["avatar"] is not None for card in first_cards)
        assert all(card["source"] == "Phoenix Yin @Phoenixyin13" for card in first_cards)
        assert all(card["story_has_media"] is with_media for card in first_cards)
        assert bool(first_cards[0]["attachments"]) is with_media
        assert all(not card["attachments"] for card in first_cards[1:])
        assert renderer.cards[: len(pages)] == first_cards
        expected_stories = 2 if room_for_next and not five_star else 1
        assert sink.notes[0].body.splitlines() == [
            f"第{index + 1}条新闻的一句话核心总结。" for index in range(expected_stories)
        ]
        assert len(sink.notes[0].images) == len(pages) + expected_stories - 1 <= 18
        with database.locked() as connection:
            assert (
                connection.execute("SELECT count(*) FROM publication_marks").fetchone()[0]
                == expected_stories
            )


def test_x_publication_work_selects_only_x_records_and_preserves_author_label(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        now = datetime.now(UTC) - timedelta(minutes=1)
        telegram = _record("801", now, source_name="Telegram channel")
        x_post = SourceRecord(
            record_id=stable_record_id("x-main", "x-karpathy", "802"),
            source_id="x-main",
            target_id="x-karpathy",
            plugin_id="x",
            external_id="802",
            content_type="tech_news",
            occurred_at=now,
            observed_at=now,
            text="A detailed public X post about a concrete language model research result.",
            source_name="Andrej Karpathy @karpathy",
            source_url="https://x.com/karpathy/status/802",
            payload={"avatar_attachment_index": 0},
            attachments=(
                AttachmentInput("image/webp", "avatar.webp", b"RIFF0000WEBPavatar"),
                AttachmentInput("image/jpeg", "post.jpg", b"\xff\xd8\xffpost"),
            ),
        )
        records.commit_batch(
            CollectBatch("telegram-main", "telegram-target", (telegram,), {"max_message_id": 801})
        )
        records.commit_batch(CollectBatch("x-main", "x-karpathy", (x_post,), {}))
        processor = FakeProcessor()
        renderer = FakeNewsRenderer(runtime_root / "generated")
        sink = FakeNewsSink()
        _work_items, work = _claimed_work(
            database,
            payload={
                "reason": "threshold",
                "source_plugin": "x",
                "presentation": "original_with_chinese_translation",
                "card_template": "x_post.html",
            },
        )

        outcome = asyncio.run(
            _service(
                records=records,
                database=database,
                runtime_root=runtime_root,
                processor=processor,
                renderer=renderer,
                sink=sink,
                capacity=7,
            )(work)
        )

        assert outcome == "published"
        assert [candidate.source_name for candidate in processor.candidates] == [
            "Andrej Karpathy @karpathy"
        ]
        assert renderer.cards[0]["source"] == "Andrej Karpathy @karpathy"
        assert renderer.cards[0]["avatar"].file_name == "avatar.webp"
        assert renderer.cards[0]["attachments"][0].file_name == "post.jpg"
        assert renderer.cards[0]["template_name"] == "x_post.html"
        assert processor.preserve_original is True
        assert len(sink.notes) == 1
    finally:
        database.close()


def test_scheduled_route_compares_both_sources_but_publishes_one_x_styled_card(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        now = datetime.now(UTC)
        x_post = SourceRecord(
            record_id=stable_record_id("x-main", "x-author", "901"),
            source_id="x-main",
            target_id="x-author",
            plugin_id="x",
            external_id="901",
            content_type="tech_news",
            occurred_at=now - timedelta(minutes=2),
            observed_at=now,
            text="A concrete public X post about a useful new developer tool.",
            source_name="X Author @author",
        )
        telegram = _record(
            "902",
            now - timedelta(minutes=1),
            source_name="Telegram channel",
        )
        records.upsert(x_post)
        records.upsert(telegram)
        processor = FakeProcessor()
        renderer = FakeNewsRenderer(runtime_root / "generated")
        sink = FakeNewsSink()
        _work_items, work = _claimed_work(database, payload={"reason": "scheduled"})

        outcome = asyncio.run(
            _service(
                records=records,
                database=database,
                runtime_root=runtime_root,
                processor=processor,
                renderer=renderer,
                sink=sink,
                capacity=18,
                source_presentations={"x": "original_with_chinese_translation"},
                source_card_templates={"x": "x_post.html"},
            )(work)
        )

        assert outcome == "published"
        assert [candidate.plugin_id for candidate in processor.candidates] == ["x", "telegram"]
        assert processor.max_items == 18
        assert processor.scheduled_best_only is True
        assert processor.fill_capacity is False
        assert processor.preserve_original_ids == frozenset({x_post.record_id})
        assert renderer.cards[0]["record_id"] == x_post.record_id
        assert renderer.cards[0]["template_name"] == "x_post.html"
        ledger = PublicationLedger(database)
        assert ledger.is_marked(x_post.record_id, sink="xiaohongshu", account_id="main")
        assert not ledger.is_marked(
            telegram.record_id,
            sink="xiaohongshu",
            account_id="main",
        )
    finally:
        database.close()


def test_scheduled_route_fills_eighteen_slots_with_one_five_star_cover(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        now = datetime.now(UTC)
        for index in range(20):
            records.upsert(
                _record(
                    str(1_200 + index),
                    now - timedelta(minutes=14) + timedelta(seconds=index),
                    source_name=f"telegram-{index}",
                )
            )
        processor = FakeProcessor()
        sink = FakeNewsSink()
        _work_items, work = _claimed_work(database, payload={"reason": "scheduled"})

        outcome = asyncio.run(
            _service(
                records=records,
                database=database,
                runtime_root=runtime_root,
                processor=processor,
                renderer=FakeNewsRenderer(runtime_root / "generated"),
                sink=sink,
                capacity=18,
            )(work)
        )

        assert outcome == "published"
        assert processor.fill_capacity is False
        assert processor.max_items == 18
        assert len(sink.notes[0].images) == 18
        assert processor.output_items[0].star_rating == 4
        assert all(item.star_rating <= 4 for item in processor.output_items[1:])
    finally:
        database.close()


def test_startup_publication_uses_only_the_fixed_prestart_half_hour_window(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        startup_at = datetime.now(UTC) - timedelta(seconds=1)
        old = _record("1400", startup_at - timedelta(hours=1), source_name="old")
        records.upsert(old)
        for index in range(18):
            records.upsert(
                _record(
                    str(1_401 + index),
                    startup_at - timedelta(minutes=29) + timedelta(seconds=index),
                    source_name=f"recent-{index}",
                )
            )
        processor = FakeProcessor()
        sink = FakeNewsSink()
        _work_items, work = _claimed_work(
            database,
            payload={
                "reason": "startup",
                "source_plugin": "telegram",
                "candidate_window_start": (startup_at - timedelta(minutes=30)).isoformat(),
                "candidate_window_end": startup_at.isoformat(),
            },
        )

        outcome = asyncio.run(
            _service(
                records=records,
                database=database,
                runtime_root=runtime_root,
                processor=processor,
                renderer=FakeNewsRenderer(runtime_root / "generated"),
                sink=sink,
                capacity=18,
            )(work)
        )

        assert outcome == "published"
        assert len(processor.candidates) == 18
        assert old.record_id not in {candidate.record_id for candidate in processor.candidates}
        assert len(sink.notes[0].images) == 18
        assert not PublicationLedger(database).is_marked(
            old.record_id,
            sink="xiaohongshu",
            account_id="main",
        )
    finally:
        database.close()


def test_immediate_five_star_defers_without_marking_when_llm_selects_nothing(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        pool = _insert_pool(records, datetime.now(UTC))
        processor = FakeProcessor(select=False)
        _work_items, work = _claimed_work(
            database,
            payload={"reason": "five_star", "source_plugin": "telegram"},
        )

        outcome = asyncio.run(
            _service(
                records=records,
                database=database,
                runtime_root=runtime_root,
                processor=processor,
                renderer=FakeNewsRenderer(runtime_root / "generated"),
                sink=FakeNewsSink(),
                capacity=18,
            )(work)
        )

        assert outcome == "deferred"
        assert processor.five_star_only is True
        assert (
            PublicationLedger(database).marked_record_ids(
                pool.all_record_ids,
                sink="xiaohongshu",
                account_id="main",
            )
            == set()
        )
    finally:
        database.close()


def _latest_slot(database: Database) -> dict:
    with database.locked() as connection:
        row = connection.execute(
            "SELECT * FROM publish_slots ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    assert row is not None
    return dict(row)


@pytest.mark.parametrize(
    ("capacity", "expected_cards", "selected_candidate_count"),
    [(1, 1, 1), (3, 2, 2), (7, 6, 6)],
)
def test_fresh_reserve_album_gif_and_capacity_are_preserved(
    tmp_path: Path,
    capacity: int,
    expected_cards: int,
    selected_candidate_count: int,
) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        pool = _insert_pool(records, datetime.now(UTC))
        processor = FakeProcessor()
        renderer = FakeNewsRenderer(runtime_root / "generated")
        sink = FakeNewsSink()
        work_items, work = _claimed_work(database, payload={"reason": "capacity"})
        service = _service(
            records=records,
            database=database,
            runtime_root=runtime_root,
            processor=processor,
            renderer=renderer,
            sink=sink,
            capacity=capacity,
        )

        outcome = asyncio.run(service(work))

        assert outcome == "published"
        assert processor.max_items == capacity
        assert [candidate.record_id for candidate in processor.candidates] == list(
            pool.candidate_ids
        )
        assert len(renderer.cards) == expected_cards
        assert len(sink.notes) == 1
        assert len(sink.notes[0].images) == capacity
        assert len(sink.notes[0].body.splitlines()) == selected_candidate_count
        assert sink.notes[0].allow_empty_text is False
        assert sink.notes[0].topics == ("科技", "研发")
        if capacity >= 3:
            assert sink.image_names[:3] == [
                sink.image_names[0],
                "story-01-motion-1.gif",
                sink.image_names[2],
            ]
            assert sink.image_names[0].endswith("card-1.png")
            assert sink.image_names[2].endswith("card-2.png")
            assert sink.image_bytes[1] == pool.gif_bytes
        else:
            assert all(not name.endswith(".gif") for name in sink.image_names)

        selected_candidates = pool.candidate_ids[:selected_candidate_count]
        expected_marked = {
            record_id
            for candidate_id in selected_candidates
            for record_id in pool.record_ids_by_candidate[candidate_id]
        }
        ledger = PublicationLedger(database)
        assert (
            ledger.marked_record_ids(
                pool.all_record_ids,
                sink="xiaohongshu",
                account_id="main",
            )
            == expected_marked
        )
        assert work_items.get(work.work_id).state is WorkState.SUCCEEDED
        assert _latest_slot(database)["status"] == "published"
        assert all(not path.exists() for path in renderer.paths)
    finally:
        database.close()


def test_capacity_route_defers_until_all_eighteen_image_slots_are_filled(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        pool = _insert_pool(records, datetime.now(UTC))
        processor = FakeProcessor()
        sink = FakeNewsSink()
        _work_items, work = _claimed_work(database, payload={"reason": "capacity"})

        outcome = asyncio.run(
            _service(
                records=records,
                database=database,
                runtime_root=runtime_root,
                processor=processor,
                renderer=FakeNewsRenderer(runtime_root / "generated"),
                sink=sink,
                capacity=18,
            )(work)
        )

        assert outcome == "deferred"
        assert processor.fill_capacity is True
        assert sink.notes == []
        assert (
            PublicationLedger(database).marked_record_ids(
                pool.all_record_ids,
                sink="xiaohongshu",
                account_id="main",
            )
            == set()
        )
        assert _latest_slot(database)["status"] == "deferred"
    finally:
        database.close()


def test_startup_route_publishes_an_underfilled_note_immediately(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        pool = _insert_pool(records, datetime.now(UTC))
        processor = FakeProcessor()
        sink = FakeNewsSink()
        _work_items, work = _claimed_work(database, payload={"reason": "startup"})

        outcome = asyncio.run(
            _service(
                records=records,
                database=database,
                runtime_root=runtime_root,
                processor=processor,
                renderer=FakeNewsRenderer(runtime_root / "generated"),
                sink=sink,
                capacity=18,
            )(work)
        )

        assert outcome == "published"
        assert processor.fill_capacity is True
        assert processor.scheduled_best_only is True
        assert len(sink.notes) == 1
        assert 1 <= len(sink.notes[0].images) < 18
        assert PublicationLedger(database).marked_record_ids(
            pool.all_record_ids,
            sink="xiaohongshu",
            account_id="main",
        )
    finally:
        database.close()


def test_five_star_route_puts_following_news_into_the_same_note(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        _insert_pool(records, datetime.now(UTC))
        processor = FakeProcessor()
        sink = FakeNewsSink()
        _work_items, work = _claimed_work(
            database,
            payload={"reason": "five_star", "source_plugin": "telegram"},
        )

        outcome = asyncio.run(
            _service(
                records=records,
                database=database,
                runtime_root=runtime_root,
                processor=processor,
                renderer=FakeNewsRenderer(runtime_root / "generated"),
                sink=sink,
                capacity=18,
            )(work)
        )

        assert outcome == "published"
        assert processor.five_star_only is True
        assert processor.fill_capacity is True
        assert processor.max_items == 18
        assert len(sink.notes) == 1
        assert len(sink.notes[0].images) > 1
    finally:
        database.close()


def test_empty_filter_marks_every_evaluated_fresh_and_reserve_record_skipped(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        pool = _insert_pool(records, datetime.now(UTC))
        processor = FakeProcessor(select=False)
        sink = FakeNewsSink()
        work_items, work = _claimed_work(database)
        outcome = asyncio.run(
            _service(
                records=records,
                database=database,
                runtime_root=runtime_root,
                processor=processor,
                renderer=FakeNewsRenderer(runtime_root / "generated"),
                sink=sink,
                capacity=7,
            )(work)
        )
        assert outcome == "filtered"
        # PublisherWorker performs this final local transition after a handler returns.
        assert work_items.succeed(work.work_id)

        ledger = PublicationLedger(database)
        assert ledger.marked_record_ids(
            pool.all_record_ids,
            sink="xiaohongshu",
            account_id="main",
        ) == set(pool.all_record_ids)
        with database.locked() as connection:
            statuses = {
                row[0]
                for row in connection.execute("SELECT DISTINCT status FROM publication_marks")
            }
            assert statuses == {"skipped"}
            assert connection.execute("SELECT count(*) FROM remote_operations").fetchone()[0] == 0
        assert sink.notes == []
        assert _latest_slot(database)["status"] == "filtered"
    finally:
        database.close()


def test_scheduled_route_filters_unpublishable_candidates_after_llm_retry(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        pool = _insert_pool(records, datetime.now(UTC))
        processor = FakeProcessor(select=False)
        sink = FakeNewsSink()
        _work_items, work = _claimed_work(
            database,
            payload={"reason": "scheduled"},
        )

        outcome = asyncio.run(
            _service(
                records=records,
                database=database,
                runtime_root=runtime_root,
                processor=processor,
                renderer=FakeNewsRenderer(runtime_root / "generated"),
                sink=sink,
                capacity=18,
            )(work)
        )

        assert outcome == "filtered"
        assert processor.scheduled_best_only is True
        assert processor.max_items == 18
        assert PublicationLedger(database).marked_record_ids(
            pool.all_record_ids,
            sink="xiaohongshu",
            account_id="main",
        ) == set(pool.all_record_ids)
        assert sink.notes == []
        assert _latest_slot(database)["status"] == "filtered"
    finally:
        database.close()


def test_render_failure_before_fences_leaves_candidates_unmarked(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        pool = _insert_pool(records, datetime.now(UTC))
        work_items, work = _claimed_work(database)
        service = _service(
            records=records,
            database=database,
            runtime_root=runtime_root,
            processor=FakeProcessor(),
            renderer=FakeNewsRenderer(
                runtime_root / "generated", failure=RuntimeError("render failed")
            ),
            sink=FakeNewsSink(),
            capacity=3,
        )

        with pytest.raises(RuntimeError, match="render failed"):
            asyncio.run(service(work))

        assert (
            PublicationLedger(database).marked_record_ids(
                pool.all_record_ids,
                sink="xiaohongshu",
                account_id="main",
            )
            == set()
        )
        assert work_items.get(work.work_id).state is WorkState.RUNNING
        with database.locked() as connection:
            assert connection.execute("SELECT count(*) FROM remote_operations").fetchone()[0] == 0
        assert _latest_slot(database)["status"] == "failed"
    finally:
        database.close()


def test_daily_limit_releases_candidates_and_holds_remote_circuit(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        pool = _insert_pool(records, datetime.now(UTC))
        work_items, work = _claimed_work(database)
        outcome = asyncio.run(
            _service(
                records=records,
                database=database,
                runtime_root=runtime_root,
                processor=FakeProcessor(),
                renderer=FakeNewsRenderer(runtime_root / "generated"),
                sink=FakeNewsSink(
                    failure=SinkFailure(
                        "今日发布数达到上限，请明天再试试",
                        submission_started=True,
                        code="XHS_DAILY_LIMIT",
                    )
                ),
                capacity=1,
            )(work)
        )

        assert outcome == "rate_limited"
        assert work_items.get(work.work_id).state is WorkState.WAITING_OPERATOR
        remote = RemoteOperationRepository(database).unresolved()
        assert len(remote) == 1
        assert remote[0].state == "RATE_LIMITED"
        assert (
            PublicationLedger(database).marked_record_ids(
                pool.all_record_ids,
                sink="xiaohongshu",
                account_id="main",
            )
            == set()
        )
        assert _latest_slot(database)["status"] == "rate-limited"
    finally:
        database.close()


def test_http_461_releases_candidates_and_holds_anti_bot_circuit(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        pool = _insert_pool(records, datetime.now(UTC))
        work_items, work = _claimed_work(database)
        outcome = asyncio.run(
            _service(
                records=records,
                database=database,
                runtime_root=runtime_root,
                processor=FakeProcessor(),
                renderer=FakeNewsRenderer(runtime_root / "generated"),
                sink=FakeNewsSink(
                    failure=SinkFailure(
                        "Xiaohongshu rejected the submission with HTTP 461",
                        submission_started=True,
                        code="XHS_ANTI_BOT",
                    )
                ),
                capacity=1,
            )(work)
        )

        assert outcome == "rate_limited"
        assert work_items.get(work.work_id).state is WorkState.WAITING_OPERATOR
        remote = RemoteOperationRepository(database).unresolved()
        assert len(remote) == 1
        assert remote[0].state == "RATE_LIMITED"
        assert (
            PublicationLedger(database).marked_record_ids(
                pool.all_record_ids,
                sink="xiaohongshu",
                account_id="main",
            )
            == set()
        )
        assert _latest_slot(database)["status"] == "rate-limited"
    finally:
        database.close()


def test_explicit_remote_rejection_skips_batch_without_opening_circuit(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        pool = _insert_pool(records, datetime.now(UTC))
        work_items, work = _claimed_work(database)

        outcome = asyncio.run(
            _service(
                records=records,
                database=database,
                runtime_root=runtime_root,
                processor=FakeProcessor(),
                renderer=FakeNewsRenderer(runtime_root / "generated"),
                sink=FakeNewsSink(
                    failure=SinkFailure(
                        "note manager total did not increase",
                        submission_started=True,
                        code="XHS_REMOTE_REJECTED",
                    )
                ),
                capacity=1,
            )(work)
        )

        assert outcome == "rejected"
        assert work_items.get(work.work_id).state is WorkState.REJECTED
        assert RemoteOperationRepository(database).unresolved() == []
        assert PublicationLedger(database).marked_record_ids(
            pool.all_record_ids,
            sink="xiaohongshu",
            account_id="main",
        ) == set(pool.record_ids_by_candidate[pool.candidate_ids[0]])
        assert _latest_slot(database)["status"] == "rejected"
    finally:
        database.close()


@pytest.mark.parametrize(
    ("submission_started", "work_state", "slot_status", "mark_status", "remote_state"),
    [
        (False, WorkState.RETRY_WAIT, "failed", None, "NOT_SUBMITTED"),
        (True, WorkState.RECONCILE_ONLY, "publish-failed", "failed", "AMBIGUOUS"),
    ],
)
def test_remote_failure_respects_pre_and_post_submission_fences(
    tmp_path: Path,
    submission_started: bool,
    work_state: WorkState,
    slot_status: str,
    mark_status: str | None,
    remote_state: str,
) -> None:
    runtime_root = tmp_path / "runtime"
    database = Database(runtime_root / "app.sqlite3")
    migrate(database)
    try:
        records = RecordsRepository(database, runtime_root)
        pool = _insert_pool(records, datetime.now(UTC))
        work_items, work = _claimed_work(database)
        service = _service(
            records=records,
            database=database,
            runtime_root=runtime_root,
            processor=FakeProcessor(),
            renderer=FakeNewsRenderer(runtime_root / "generated"),
            sink=FakeNewsSink(
                failure=SinkFailure("Safari interrupted", submission_started=submission_started)
            ),
            capacity=1,
        )

        outcome = asyncio.run(service(work))

        assert outcome == ("ambiguous" if submission_started else "not_submitted")
        assert work_items.get(work.work_id).state is work_state
        if not submission_started:
            retry_at = datetime.fromisoformat(
                work_items.get(work.work_id).next_retry_at.replace("Z", "+00:00")
            )
            assert 50 <= (retry_at - datetime.now(UTC)).total_seconds() <= 60
        marked = PublicationLedger(database).marked_record_ids(
            pool.all_record_ids,
            sink="xiaohongshu",
            account_id="main",
        )
        if mark_status is None:
            assert marked == set()
        else:
            assert marked == set(pool.record_ids_by_candidate[pool.candidate_ids[0]])
            with database.locked() as connection:
                assert (
                    connection.execute("SELECT DISTINCT status FROM publication_marks").fetchone()[
                        0
                    ]
                    == mark_status
                )
        with database.locked() as connection:
            assert (
                connection.execute("SELECT state FROM remote_operations").fetchone()[0]
                == remote_state
            )
        assert _latest_slot(database)["status"] == slot_status
    finally:
        database.close()
