from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer

from xhs_local.core.contracts import AttachmentInput, CollectBatch, SourceRecord
from xhs_local.storage.checkpoints import CheckpointRepository
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.schema import open_database
from xhs_local.website import WebsiteCollector, WebsitePosters, clean_expired_news, create_website


def record(key, *, when=None, plugin="x", text="未经审核的原始新闻", images=()):
    now = datetime.now(UTC)
    return SourceRecord(
        record_id=key,
        source_id="source",
        target_id="target",
        plugin_id=plugin,
        external_id=key,
        content_type="tech_news",
        occurred_at=when or now,
        observed_at=now,
        text=text,
        source_name="作者",
        source_url="https://example.com/post",
        attachments=images,
    )


def test_collection_is_immediately_public_without_review_or_work_and_respects_reset(tmp_path):
    async def run():
        with open_database(tmp_path / "app.sqlite3", apply_migrations=True) as db:
            records = RecordsRepository(db, tmp_path)
            cutoff = datetime.now(UTC) - timedelta(minutes=1)
            collector = WebsiteCollector(records, cutoff)
            old = record("old", when=cutoff - timedelta(seconds=1))
            new = record("new")
            video = replace(
                record("video", plugin="youtube"),
                content_type="video_pending",
                title="新视频",
                text="",
                payload={
                    "video_metadata": {
                        "timestamp": datetime.now(UTC).timestamp(),
                    }
                },
            )
            old_video = replace(
                video,
                record_id="old-video",
                external_id="old-video",
                payload={
                    "video_metadata": {
                        "timestamp": (cutoff - timedelta(days=1)).timestamp(),
                    }
                },
            )
            batch = CollectBatch("source", "target", (old, new, video, old_video), {"cursor": 4})
            result = await collector.commit(batch, config_revision="test")
            assert set(result.inserted_record_ids) == {"new", "video"}
            assert result.work_ids == ()
            assert records.news_feed()["total"] == 2
            assert CheckpointRepository(db).get("source", "target") == {"cursor": 4}
            assert db.connection.execute("SELECT count(*) FROM work_items").fetchone()[0] == 0
            assert db.connection.execute("SELECT count(*) FROM outbox").fetchone()[0] == 0
            assert not (await collector.commit(batch, config_revision="test")).inserted_record_ids

    asyncio.run(run())


def test_website_api_filters_paginates_serves_only_news_images_and_saves_favorites(tmp_path):
    async def run():
        with open_database(tmp_path / "app.sqlite3", apply_migrations=True) as db:
            records = RecordsRepository(db, tmp_path)
            for i in range(32):
                records.upsert(record(f"x-{i}", text=f"帖子 {i}"))
            image = AttachmentInput("image/png", "photo.png", b"PNG-photo")
            entry = replace(
                record(
                    "telegram",
                    plugin="telegram",
                    text="测试 <script>evil()</script>",
                    images=(image,),
                ),
                payload={"secret": "private-token"},
            )
            records.upsert(entry)
            records.upsert(replace(record("private", images=(image,)), content_type="document"))
            private_media = records.get("private").attachments[0].attachment_id
            async with TestClient(TestServer(create_website(records))) as client:
                response = await client.get("/")
                assert response.status == 200
                assert "Newsroom" in await response.text()
                feed = await (await client.get("/api/news")).json()
                assert feed["total"] == 33 and len(feed["items"]) == 30
                second = await (await client.get("/api/news?page=2")).json()
                assert len(second["items"]) == 3
                assert not {i["record_id"] for i in feed["items"]} & {
                    i["record_id"] for i in second["items"]
                }
                filtered = await (await client.get("/api/news?source=telegram&q=测试")).json()
                assert filtered["total"] == 1
                assert "private-token" not in str(filtered)
                media = await client.get(filtered["items"][0]["images"][0])
                assert media.status == 200 and await media.read() == b"PNG-photo"
                assert (await client.get(f"/media/{private_media}")).status == 404
                for path in (
                    "/runtime/secrets/key",
                    "/media/../../secrets/key",
                    "/config/app.yaml",
                ):
                    assert (await client.get(path)).status == 404
                for value in ("0", "-1", "bad", "1000001"):
                    assert (await client.get(f"/api/news?page={value}")).status == 400
                saved = await client.put("/api/news/telegram/favorite", json={"favorite": True})
                assert saved.status == 200
                favorites = await (await client.get("/api/news?favorites=1")).json()
                assert favorites["total"] == favorites["favorite_count"] == 1
                assert favorites["items"][0]["favorite"] is True
                assert (
                    await client.put("/api/news/missing/favorite", json={"favorite": True})
                ).status == 404
                assert (
                    await client.put("/api/news/telegram/favorite", json={"favorite": "true"})
                ).status == 400
                assert (
                    await client.put("/api/news/telegram/favorite", data='{"favorite":true}')
                ).status == 415
                assert (await client.get("/health/ready")).status == 200

    asyncio.run(run())


def test_cleanup_removes_expired_favorites_and_assets_but_keeps_last_two_days(tmp_path):
    now = datetime.now(UTC)
    image = AttachmentInput("image/png", "old.png", b"expired-only")
    with open_database(tmp_path / "app.sqlite3", apply_migrations=True) as db:
        records = RecordsRepository(db, tmp_path)
        records.upsert(record("expired", when=now - timedelta(days=3), images=(image,)))
        records.upsert(record("saved", when=now - timedelta(days=3)))
        records.upsert(record("recent", when=now - timedelta(hours=47)))
        path = records.get("expired").attachments[0].absolute_path(tmp_path)
        records.set_news_favorite("saved", True)
        from xhs_local.storage.video_artifacts import VideoArtifacts
        videos = VideoArtifacts(tmp_path, "x", "expired").root
        (videos / "state.json").write_text('{"record_id":"expired"}')
        (videos / "audio.mp3").write_bytes(b"old audio")
        protected = tmp_path / "secrets/key"
        protected.parent.mkdir()
        protected.write_text("secret fixture")
        assert clean_expired_news(records, now) == {"records": 2, "media": 1}
        assert records.get("expired") is None and records.get("saved") is None
        assert records.get("recent") is not None
        assert not path.exists() and not videos.exists() and protected.exists()
        assert records.news_feed()["total"] == 1
        db.quick_check()


def test_website_mode_never_constructs_legacy_review_or_publishing(monkeypatch):
    from xhs_local import app, website

    called = []

    async def run(snapshot):
        called.append(snapshot.app.website.enabled)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("website must not start the legacy pipeline")

    monkeypatch.setattr(website, "run_website", run)
    snapshot = app.load_snapshot(Path(__file__).resolve().parents[2] / "config")
    snapshot = replace(snapshot, app=snapshot.app.model_copy(update={
        "website": snapshot.app.website.model_copy(update={"enabled": True})
    }))
    monkeypatch.setattr(app, "load_snapshot", lambda _: snapshot)
    asyncio.run(app.run_application(Path(__file__).resolve().parents[2] / "config"))
    assert called == [True]


def test_website_preflight_does_not_require_models_or_remote_sink(tmp_path, monkeypatch):
    from xhs_local import cli
    from xhs_local.configuration.loader import load_snapshot

    snapshot = load_snapshot(Path(__file__).resolve().parents[2] / "config")
    snapshot = replace(
        snapshot,
        config_root=tmp_path,
        app=snapshot.app.model_copy(update={
            "database_path": "app.sqlite3",
            "website": snapshot.app.website.model_copy(update={"enabled": True}),
        }),
        sources=snapshot.sources.model_copy(update={"sources": ()}),
    )
    open_database(snapshot.database_path, apply_migrations=True).close()
    monkeypatch.setattr(cli, "_snapshot", lambda: snapshot)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("website preflight must not require LLMs or remote publishing")

    monkeypatch.setattr("xhs_local.processing.provider.DeepSeekProvider", forbidden)
    assert asyncio.run(cli.check()) == 0


def test_delete_removes_favorite_media_posters_and_never_reimports_after_restart(tmp_path):
    image = AttachmentInput("image/png", "photo.png", b"deleted-photo")
    item = record("delete-me", images=(image,))

    async def remove():
        with open_database(tmp_path / "app.sqlite3", apply_migrations=True) as db:
            records = RecordsRepository(db, tmp_path)
            records.upsert(item)
            records.set_news_favorite(item.record_id, True)
            photo = records.get(item.record_id).attachments[0]
            directory = WebsitePosters(records).directory(item.record_id)
            directory.mkdir(parents=True)
            (directory / "card.png").write_bytes(b"cached-poster")
            async with TestClient(TestServer(create_website(records))) as client:
                response = await client.delete("/api/news/delete-me")
                assert response.status == 204
                assert (await client.delete("/api/news/delete-me")).status == 204
                assert (await (await client.get("/api/news")).json())["total"] == 0
                assert (await (await client.get("/api/news?favorites=1")).json())["total"] == 0
                assert (await client.get(f"/media/{photo.attachment_id}")).status == 404
                assert (await client.get("/api/news/delete-me/cards")).status == 404
                assert (await client.get("/posters/delete-me/card.png")).status == 404
            assert not photo.absolute_path(tmp_path).exists()
            assert not directory.exists()
            assert db.connection.execute("SELECT count(*) FROM record_versions").fetchone()[0] == 0
        with open_database(tmp_path / "app.sqlite3") as db:
            records = RecordsRepository(db, tmp_path)
            result = await WebsiteCollector(records, datetime(1970, 1, 1, tzinfo=UTC)).commit(
                CollectBatch("source", "target", (item,), {"cursor": 1}), config_revision="test"
            )
            assert not result.inserted_record_ids
            assert records.news_feed()["total"] == 0
            assert records.deleted_news_ids((item.record_id,)) == {item.record_id}
            assert not photo.absolute_path(tmp_path).exists()
            assert CheckpointRepository(db).get("source", "target") == {"cursor": 1}

    asyncio.run(remove())


def test_posters_reuse_original_renderer_pagination_and_cache(tmp_path, monkeypatch):
    from xhs_local import website

    rendered = []
    measured = []

    class Renderer:
        def __init__(self, *, output_dir, runtime_root):
            self.output_dir = output_dir

        async def paginate_x_story(self, text, **kwargs):
            measured.append((text, kwargs))
            return [text[:3], text[3:]]

        async def generate_news_cards(self, cards):
            rendered.append(cards)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            result = []
            for index, _card in enumerate(cards):
                path = self.output_dir / f"page-{index}.png"
                path.write_bytes(b"PNG-rendered")
                result.append(path)
            return result

    monkeypatch.setattr(website, "HtmlPhotoGenerator", Renderer)

    async def run():
        with open_database(tmp_path / "app.sqlite3", apply_migrations=True) as db:
            records = RecordsRepository(db, tmp_path)
            records.upsert(record("x-post", images=(AttachmentInput("image/png", "a", b"image"),)))
            records.upsert(record("telegram-post", plugin="telegram"))
            async with TestClient(TestServer(create_website(records))) as client:
                first = await (await client.get("/api/news/x-post/cards")).json()
                second = await (await client.get("/api/news/x-post/cards")).json()
                assert first == second and len(first["images"]) == 2
                assert len(rendered) == len(measured) == 1
                assert [card["story_page"] for card in rendered[0]] == [1, 2]
                assert all(card["template_name"] == "x_post.html" for card in rendered[0])
                assert rendered[0][0]["attachments"] and not rendered[0][1]["attachments"]
                assert "".join(card["text"] for card in rendered[0]) == "未经审核的原始新闻"
                assert (await client.get(first["images"][0])).status == 200
                assert (await client.get("/posters/x-post/..%2F..%2F..%2Fsecret.png")).status == 404
                assert (await client.get("/api/news/telegram-post/cards")).status == 200
                assert rendered[1][0]["template_name"] is None
                assert len(measured) == 1

    asyncio.run(run())


def test_cleanup_deletes_expired_posters_including_favorites(tmp_path):
    now = datetime.now(UTC)
    with open_database(tmp_path / "app.sqlite3", apply_migrations=True) as db:
        records = RecordsRepository(db, tmp_path)
        posters = WebsitePosters(records)
        for key in ("expired", "saved"):
            records.upsert(record(key, when=now - timedelta(days=8)))
            directory = posters.directory(key)
            directory.mkdir(parents=True)
            (directory / "card.png").write_bytes(b"PNG")
        records.set_news_favorite("saved", True)
        clean_expired_news(records, now)
        assert not posters.directory("expired").exists()
        assert not posters.directory("saved").exists()
