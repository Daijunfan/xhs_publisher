from __future__ import annotations

import asyncio
import base64
import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from xhs_local.configuration.loader import load_snapshot, snapshot_data, snapshot_from_data
from xhs_local.core.contracts import AttachmentInput, SourceRecord
from xhs_local.pipeline.agents import AgentsPublisher, CollectorRequestError
from xhs_local.pipeline.source_scheduler import SourceScheduler
from xhs_local.plugins.registry import SourcePluginRegistry
from xhs_local.storage.checkpoints import CheckpointRepository
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.schema import open_database
from xhs_local.website import (
    WebsiteCollector,
    WebsiteSubscriptions,
    clean_expired_news,
    create_website,
)

ROOT = Path(__file__).resolve().parents[2]


def config(tmp_path, endpoint):
    # Only public publishing defaults are reused; every credential and source is synthetic.
    data = snapshot_data(load_snapshot(ROOT / "config"))
    data["sources"] = {
        "version": 1,
        "sources": [
            {
                "id": "x-local",
                "plugin": "x",
                "enabled": True,
                "poll_seconds": 3600,
                "options": {
                    "request_timeout_seconds": 20,
                    "lookback_hours": 48,
                    "max_concurrency": 1,
                    "max_posts_per_target": 20,
                    "max_images_per_post": 8,
                    "max_image_bytes": 8388608,
                },
                "targets": [
                    {"id": "one", "locator": "Example", "name": "Example"},
                    {
                        "id": "kept-disabled",
                        "locator": "Disabled",
                        "name": "Disabled",
                        "enabled": False,
                    },
                ],
            },
            {
                "id": "tg-local",
                "plugin": "telegram",
                "enabled": True,
                "poll_seconds": 300,
                "options": {
                    "api_id": 123,
                    "api_hash": "fixture-secret",
                    "session_path": "session",
                    "lookback_hours": 48,
                    "default_post_limit": 10,
                    "max_image_bytes": 8388608,
                    "fetch_timeout_seconds": 20,
                    "media_timeout_seconds": 20,
                },
                "targets": [{"id": "tg-one", "locator": "sample", "name": "Sample"}],
            },
        ],
    }
    data["app"].update(
        {
            "runtime_root": "../runtime",
            "database_path": "../runtime/app.sqlite3",
            "agents": {
                "enabled": True,
                "endpoint": endpoint,
                "token_file": "../token",
                "poll_seconds": 0.05,
            },
        }
    )
    root = tmp_path / "config"
    root.mkdir()
    (root / "session").write_bytes(b"fixture-session")
    (tmp_path / "token").write_text("fixture-token")
    for name, value in data.items():
        (root / f"{name}.yaml").write_text(yaml.safe_dump(value, sort_keys=False))
    return snapshot_from_data(root, data)


def target(key="one", *, enabled=True, plugin="x", poll=3600):
    return {
        "sourceId": "core-" + key,
        "targetId": key,
        "plugin": plugin,
        "locator": "Example" if plugin == "x" else "sample",
        "name": "Author " + key,
        "enabled": enabled,
        "pollSeconds": poll,
    }


def record(key="post", *, when=None, text="complete original text", images=()):
    now = datetime.now(UTC)
    return SourceRecord(
        record_id="local-" + key,
        source_id="x-local",
        target_id="one",
        plugin_id="x",
        external_id="platform-" + key,
        content_type="tech_news",
        occurred_at=when or now,
        observed_at=now,
        title="Original title",
        text=text,
        source_name="Original author",
        source_url="https://x.com/Example/status/1",
        attachments=images,
    )


class SleepingPlugin:
    async def collect(self, _request):
        await asyncio.Event().wait()

    async def close(self):
        pass


class OfflineRegistry(SourcePluginRegistry):
    def create(self, _prepared, **_kwargs):
        return SleepingPlugin()


class Core:
    def __init__(self):
        self.revision = 1
        self.targets = [
            target(),
            target("kept-disabled", enabled=False),
            target("tg-one", plugin="telegram"),
        ]
        self.requests = []
        self.fail_config = False
        self.fail_publish = False
        self.media = {}
        self.posts = {}
        self.response_status = {}
        self.reject_and_disable = False
        self.rejected_ids = set()
        self.media_errors = {}
        self.source_avatars = {}
        self.fail_avatar = False

    async def request(self, request):
        assert request.headers["Authorization"] == "Bearer fixture-token"
        body = await request.json()
        assert set(body) == {"cmd", "args"}
        self.requests.append(body)
        cmd, args = body["cmd"], body["args"]
        if cmd == "channel.collector-config":
            if self.fail_config:
                return web.json_response({"ok": False, "error": "unavailable"}, status=503)
            changed = args.get("sinceRevision") != self.revision
            result = {"revision": self.revision, "changed": changed}
            if changed:
                result["targets"] = self.targets
        elif cmd == "channel.source-avatar-put":
            if self.fail_avatar:
                return web.json_response({"ok": False, "error": "try later"}, status=503)
            assert set(args) == {"sourceId", "name", "mimeType", "data"}
            self.source_avatars[args["sourceId"]] = args
            result = {
                "sourceId": args["sourceId"],
                "sha256": hashlib.sha256(base64.b64decode(args["data"])).hexdigest(),
            }
        elif cmd == "channel.media-put":
            if args["externalId"] in self.media_errors:
                return web.json_response(
                    {
                        "ok": False,
                        "code": self.media_errors[args["externalId"]],
                        "error": "private response detail must not be retained",
                    },
                    status=410,
                )
            key = (args["sourceId"], args["externalId"], args["mediaKey"])
            data = base64.b64decode(args["data"])
            duplicate = key in self.media
            media = self.media.setdefault(
                key,
                {
                    "id": "media-" + hashlib.sha256(data).hexdigest(),
                    "name": args["name"],
                    "mimeType": args["mimeType"],
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                },
            )
            result = {"media": media, "duplicate": duplicate}
        elif cmd == "channel.publish":
            if args["externalId"] in self.rejected_ids:
                return web.json_response({"ok": False, "error": "invalid item"})
            if self.reject_and_disable:
                self.targets[0] = target(enabled=False)
                self.revision += 1
                self.reject_and_disable = False
                return web.json_response({"ok": False, "error": "disabled"})
            if self.fail_publish:
                return web.json_response({"ok": False, "error": "try later"}, status=503)
            key = (args["sourceId"], args["externalId"])
            previous = self.posts.get(key)
            status = self.response_status.get(args["externalId"]) or (
                "created"
                if previous is None
                else "duplicate"
                if previous["contentHash"] == args["contentHash"]
                else "updated"
            )
            if status not in {"deleted", "expired"}:
                self.posts[key] = args
            result = {
                "id": "news",
                "channelId": "channel",
                "status": status,
                "contentHash": args["contentHash"],
                "expiresAt": args["publishedAt"] + 48 * 3600000,
            }
        else:
            raise AssertionError(cmd)
        return web.json_response({"ok": True, "data": result})

    def application(self):
        app = web.Application(client_max_size=12 * 1024 * 1024)
        app.router.add_post("/api/channels/collector", self.request)
        return app


def test_managed_config_is_authoritative_hot_and_preserves_local_options(tmp_path):
    async def run():
        core = Core()
        async with TestServer(core.application()) as server:
            snapshot = config(tmp_path, str(server.make_url("")).rstrip("/"))
            with open_database(snapshot.database_path, apply_migrations=True) as db:
                records = RecordsRepository(db, snapshot.runtime_root)

                async def on_batch(*_args):
                    pass

                scheduler = SourceScheduler(
                    snapshot,
                    OfflineRegistry(),
                    CheckpointRepository(db),
                    WebsiteCollector(records, datetime(1970, 1, 1, tzinfo=UTC)),
                    on_batch,
                )
                subscriptions = WebsiteSubscriptions(scheduler, records)
                status = {}
                bridge = AgentsPublisher(
                    snapshot, records, subscriptions.apply_agents_targets, status.update
                )
                try:
                    await bridge.start()
                    first = scheduler.tasks["one"]
                    tg = scheduler.tasks["tg-one"]
                    assert (
                        scheduler.snapshot.sources.sources[1].options["api_hash"]
                        == "fixture-secret"
                    )
                    assert not subscriptions.following("x-local", "kept-disabled")
                    assert bridge.targets[("x", "one")].sourceId == "core-one"
                    assert "fixture-secret" not in str(core.requests)
                    await bridge.refresh_config()
                    assert core.requests[-1]["args"] == {"sinceRevision": 1}
                    assert scheduler.tasks["one"] is first
                    core.targets.append(target("new", poll=90))
                    core.revision += 1
                    await bridge.refresh_config()
                    assert scheduler.tasks["one"] is first and scheduler.tasks["tg-one"] is tg
                    assert scheduler.tasks["new"] is not first
                    assert (
                        next(
                            t
                            for t in scheduler.snapshot.sources.sources[0].targets
                            if t.id == "new"
                        ).poll_seconds
                        == 90
                    )
                    core.targets[0] = target(enabled=False)
                    core.revision += 1
                    await bridge.refresh_config()
                    assert "one" not in scheduler.tasks and first.cancelled()
                    assert scheduler.tasks["tg-one"] is tg
                    assert not subscriptions.following("x-local", "one")
                    saved = load_snapshot(snapshot.config_root)
                    assert saved.sources.sources[1].options["api_hash"] == "fixture-secret"
                    assert any(
                        t.id == "kept-disabled" and not t.enabled
                        for t in saved.sources.sources[0].targets
                    )
                    async with TestClient(
                        TestServer(create_website(records, subscriptions))
                    ) as website:
                        response = await website.post(
                            "/api/subscriptions", json={"links": ["https://x.com/New"]}
                        )
                        assert response.status == 409
                        assert (await website.delete("/api/news/missing/author")).status == 409
                        assert (await website.get("/api/news")).status == 200
                    # Startup disconnection reuses only the last confirmed public Core config.
                    await bridge.close()
                    core.fail_config = True
                    restart = AgentsPublisher(
                        snapshot, records, subscriptions.apply_agents_targets, status.update
                    )
                    try:
                        await restart.start()
                        assert restart.revision == 3 and not status["agents"]["connected"]
                        assert not restart.targets[("x", "one")].enabled
                    finally:
                        await restart.close()
                finally:
                    await bridge.close()
                    await scheduler.stop()

    asyncio.run(run())


def test_publish_media_retry_restart_ttl_reversion_and_revocation(tmp_path):
    async def run():
        core = Core()
        async with TestServer(core.application()) as server:
            snapshot = config(tmp_path, str(server.make_url("")).rstrip("/"))
            with open_database(snapshot.database_path, apply_migrations=True) as db:
                records = RecordsRepository(db, snapshot.runtime_root)
                applied, status = [], {}

                async def apply(targets):
                    applied.append(targets)

                bridge = AgentsPublisher(snapshot, records, apply, status.update)
                stop = asyncio.Event()
                image = AttachmentInput("image/png", "image.png", b"fixture-image")
                avatar = AttachmentInput("image/jpeg", "avatar.jpg", b"fixture-avatar")
                ignored = AttachmentInput("application/octet-stream", "ignored.bin", b"not-image")
                item = replace(
                    record(images=(image, avatar, ignored)),
                    payload={"avatar_attachment_index": 1, "secret": "not-exported"},
                )
                records.upsert(item)
                records.upsert(record("old", when=datetime.now(UTC) - timedelta(hours=49)))
                records.upsert(record("cloud-kept", when=datetime.now(UTC) - timedelta(days=6)))
                try:
                    await bridge.start()
                    core.fail_publish = True
                    await bridge.publish_pending(stop)
                    assert status["agents"]["error"]
                    assert not list(
                        db.connection.execute(
                            "SELECT * FROM publication_marks WHERE sink='agents-company'"
                        )
                    )
                    assert len(core.media) == 2
                    core.fail_publish = False
                    await bridge.publish_pending(stop)
                    assert set(core.posts) == {("core-one", "platform-post")}
                    published = core.posts[("core-one", "platform-post")]
                    assert published["body"] == item.text and published["publishedAt"] == int(
                        item.occurred_at.timestamp() * 1000
                    )
                    assert len(published["mediaIds"]) == 1 and published["avatarMediaId"]
                    assert "not-exported" not in str(core.requests)
                    assert len(core.media) == 2, "retries reuse media identity"
                    count = len(core.requests)
                    await bridge.publish_pending(stop)
                    assert len(core.requests) == count, "confirmed unchanged content is not resent"
                    records.upsert(replace(item, text="edited full content"))
                    await bridge.publish_pending(stop)
                    assert (
                        core.posts[("core-one", "platform-post")]["body"] == "edited full content"
                    )
                    records.upsert(item)
                    await bridge.publish_pending(stop)
                    assert core.posts[("core-one", "platform-post")]["body"] == item.text, (
                        "A-B-A reversion is published"
                    )
                    for key, terminal in [("deleted", "deleted"), ("expired", "expired")]:
                        core.response_status["platform-" + key] = terminal
                        records.upsert(record(key))
                    await bridge.publish_pending(stop)
                    count = len(core.requests)
                    records.upsert(record("deleted", text="changed after tombstone"))
                    await bridge.publish_pending(stop)
                    assert len(core.requests) == count
                    await bridge.close()
                    restart = AgentsPublisher(snapshot, records, apply, status.update)
                    try:
                        await restart.start()
                        count = len(core.requests)
                        await restart.publish_pending(stop)
                        assert len(core.requests) == count, "receipts survive publisher restart"
                        records.upsert(record("revoked"))
                        core.reject_and_disable = True
                        await restart.publish_pending(stop)
                        count = len(core.requests)
                        await restart.publish_pending(stop)
                        assert len(core.requests) == count, (
                            "revoked targets stop retrying after config refresh"
                        )
                        assert not restart.targets[("x", "one")].enabled
                    finally:
                        await restart.close()
                    # An invalid item stays retryable without starving unrelated news.
                    core.targets[0] = target()
                    core.revision += 1
                    await bridge.start()
                    records.upsert(record("bad", when=datetime.now(UTC) - timedelta(minutes=2)))
                    records.upsert(record("good", when=datetime.now(UTC) - timedelta(minutes=1)))
                    core.rejected_ids.add("platform-bad")
                    await bridge.publish_pending(stop)
                    assert ("core-one", "platform-good") in core.posts
                    assert ("core-one", "platform-bad") not in core.posts
                    assert records.get("local-old") and records.get("local-cloud-kept"), (
                        "48h export limit does not change cloud retention"
                    )
                    clean_expired_news(records, datetime.now(UTC))
                    assert records.get("local-cloud-kept") is None
                    assert (
                        db.connection.execute("SELECT count(*) FROM work_items").fetchone()[0] == 0
                    )
                    assert db.connection.execute("SELECT count(*) FROM outbox").fetchone()[0] == 0
                finally:
                    await bridge.close()

    asyncio.run(run())


def test_first_start_requires_core_and_stop_closes_without_publishing(tmp_path):
    async def run():
        core = Core()
        core.fail_config = True
        async with TestServer(core.application()) as server:
            snapshot = config(tmp_path, str(server.make_url("")).rstrip("/"))
            with open_database(snapshot.database_path, apply_migrations=True) as db:
                records = RecordsRepository(db, snapshot.runtime_root)
                calls = []

                async def apply(targets):
                    calls.append(targets)

                bridge = AgentsPublisher(snapshot, records, apply, lambda **_fields: None)
                try:
                    with pytest.raises(CollectorRequestError):
                        await bridge.start()
                    assert not calls
                    core.fail_config = False
                    await bridge.refresh_config(force=True)
                    records.upsert(record())
                    stop = asyncio.Event()
                    stop.set()
                    await bridge.run(stop)
                    assert not core.posts
                finally:
                    await bridge.close()
                assert bridge.session is None

    asyncio.run(run())


@pytest.mark.parametrize("terminal", ["deleted", "expired"])
def test_media_terminal_receipt_is_recorded_without_retry_or_resurrection(tmp_path, terminal):
    async def run():
        core = Core()
        core.media_errors["platform-post"] = "POST_" + terminal.upper()
        core.response_status["platform-post"] = terminal
        async with TestServer(core.application()) as server:
            snapshot = config(tmp_path, str(server.make_url("")).rstrip("/"))
            with open_database(snapshot.database_path, apply_migrations=True) as db:
                records = RecordsRepository(db, snapshot.runtime_root)
                item = record(
                    images=(
                        AttachmentInput("image/png", "first.png", b"one"),
                        AttachmentInput("image/jpeg", "second.jpg", b"two"),
                    )
                )
                records.upsert(item)

                async def apply(_targets):
                    pass

                publisher = AgentsPublisher(snapshot, records, apply, lambda **_fields: None)
                try:
                    await publisher.start()
                    await publisher.publish_pending(asyncio.Event())
                    commands = [r["cmd"] for r in core.requests]
                    assert commands.count("channel.media-put") == 1
                    assert commands.count("channel.publish") == 1
                    assert not core.media and not core.posts
                    mark = db.connection.execute(
                        "SELECT status FROM publication_marks WHERE sink='agents-company'"
                    ).fetchone()
                    assert mark["status"] == terminal
                    count = len(core.requests)
                    records.upsert(replace(item, text="changed after terminal receipt"))
                    await publisher.publish_pending(asyncio.Event())
                    assert len(core.requests) == count
                finally:
                    await publisher.close()

    asyncio.run(run())


def test_other_media_errors_remain_pending_and_preserve_only_safe_code(tmp_path):
    async def run():
        core = Core()
        core.media_errors["platform-post"] = "MEDIA_INVALID"
        async with TestServer(core.application()) as server:
            snapshot = config(tmp_path, str(server.make_url("")).rstrip("/"))
            with open_database(snapshot.database_path, apply_migrations=True) as db:
                records = RecordsRepository(db, snapshot.runtime_root)
                records.upsert(record(images=(AttachmentInput("image/png", "image.png", b"bad"),)))

                async def apply(_targets):
                    pass

                publisher = AgentsPublisher(snapshot, records, apply, lambda **_fields: None)
                try:
                    await publisher.start()
                    stored = records.get("local-post")
                    with pytest.raises(CollectorRequestError) as raised:
                        await publisher._publish(stored, publisher.targets[("x", "one")])
                    assert raised.value.code == "MEDIA_INVALID"
                    assert "private response detail" not in str(raised.value)
                    assert not any(r["cmd"] == "channel.publish" for r in core.requests)
                    assert not list(
                        db.connection.execute(
                            "SELECT * FROM publication_marks WHERE sink='agents-company'"
                        )
                    )
                    await publisher.publish_pending(asyncio.Event())
                    assert sum(r["cmd"] == "channel.media-put" for r in core.requests) == 2
                finally:
                    await publisher.close()

    asyncio.run(run())


def test_managed_creator_forms_reach_real_plugin_validation_without_identity_changes(tmp_path):
    from xhs_local.configuration.models import AgentsTarget
    from xhs_local.configuration.subscriptions import source_homepage

    async def run():
        snapshot = config(tmp_path, "http://127.0.0.1:1")
        data = snapshot_data(snapshot)
        data["sources"]["sources"].append(
            {
                "id": "youtube-local",
                "plugin": "youtube",
                "enabled": True,
                "poll_seconds": 7200,
                "options": {},
                "targets": [
                    {
                        "id": "yt-existing",
                        "locator": "https://www.youtube.com/@Bootstrap",
                        "name": "Bootstrap",
                        "enabled": True,
                    }
                ],
            }
        )
        snapshot = snapshot_from_data(snapshot.config_root, data)
        for name, value in data.items():
            (snapshot.config_root / f"{name}.yaml").write_text(yaml.safe_dump(value))
        with open_database(snapshot.database_path, apply_migrations=True) as db:
            records = RecordsRepository(db, snapshot.runtime_root)

            async def on_batch(*_args):
                pass

            registry = OfflineRegistry()
            scheduler = SourceScheduler(
                snapshot,
                registry,
                CheckpointRepository(db),
                WebsiteCollector(records, datetime(1970, 1, 1, tzinfo=UTC)),
                on_batch,
            )
            subscriptions = WebsiteSubscriptions(scheduler, records)
            values = [
                target(),
                target("tg-one", plugin="telegram"),
                {
                    **target("yt-existing", plugin="youtube"),
                    "locator": "https://www.youtube.com/@Bootstrap",
                },
                {**target("x-url"), "locator": "https://x.com/WholeUrl?lang=en"},
                {**target("x-at"), "locator": "@HandleName"},
                {**target("yt-at", plugin="youtube"), "locator": "@NewCreator"},
            ]
            targets = [AgentsTarget.model_validate(value) for value in values]
            try:
                await subscriptions.apply_agents_targets(targets)
                prepared = [
                    registry.prepare(
                        source, config_root=snapshot.config_root, runtime_root=snapshot.runtime_root
                    )
                    for source in scheduler.snapshot.sources.sources
                    if source.enabled
                ]
                locators = {t.id: t.locator for source in prepared for t in source.targets}
                assert locators == {
                    "one": "Example",
                    "tg-one": "sample",
                    "yt-existing": "https://www.youtube.com/@Bootstrap",
                    "x-url": "WholeUrl",
                    "x-at": "HandleName",
                    "yt-at": "https://www.youtube.com/@NewCreator",
                }
                # prepare runs each real plugin's validate_target on normalized inputs.
                assert {source.manifest.plugin_id for source in prepared} == {
                    "x",
                    "telegram",
                    "youtube",
                }
                before = dict(scheduler.tasks)
                await subscriptions.apply_agents_targets(targets)
                assert scheduler.tasks == before, "raw Core forms do not restart normalized targets"
                assert [(t.sourceId, t.targetId) for t in targets] == [
                    (v["sourceId"], v["targetId"]) for v in values
                ]
                assert (
                    source_homepage("youtube", "@NewCreator")
                    == "https://www.youtube.com/@NewCreator"
                )
                assert source_homepage("x", "https://x.com/WholeUrl") == "https://x.com/WholeUrl"
            finally:
                await scheduler.stop()

    asyncio.run(run())


def test_source_avatar_sync_is_independent_of_posts_durable_and_retried(tmp_path):
    async def run():
        core = Core()
        async with TestServer(core.application()) as server:
            snapshot = config(tmp_path, str(server.make_url("")).rstrip("/"))
            with open_database(snapshot.database_path, apply_migrations=True) as db:
                records = RecordsRepository(db, snapshot.runtime_root)
                checkpoints = CheckpointRepository(db)
                data = b"\xff\xd8\xff\xdbsource-identity"
                avatar = {
                    "photo_id": "5",
                    "name": "avatar.jpg",
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(data).decode(),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
                checkpoints.put("tg-local", "tg-one", {"channel_avatar": avatar})
                applied = []

                async def apply(targets):
                    applied.append(targets)

                status = {}
                bridge = AgentsPublisher(snapshot, records, apply, status.update)
                try:
                    await bridge.start()
                    core.fail_avatar = True
                    await bridge.publish_avatars(asyncio.Event())
                    assert checkpoints.get("agents-company", "avatar:core-tg-one") is None
                    core.fail_avatar = False
                    await bridge.publish_avatars(asyncio.Event())
                    assert core.source_avatars["core-tg-one"]["data"] == avatar["data"]
                    assert not core.posts and not core.media
                    mark = checkpoints.get("agents-company", "avatar:core-tg-one")
                    assert mark["sha256"] == avatar["sha256"]
                    calls = len(core.requests)
                    await bridge.publish_avatars(asyncio.Event())
                    assert len(core.requests) == calls
                    await bridge.close()
                    bridge = AgentsPublisher(snapshot, records, apply, status.update)
                    await bridge.start()
                    calls = len(core.requests)
                    await bridge.publish_avatars(asyncio.Event())
                    assert len(core.requests) == calls
                    assert status["agents"]["avatars_synced"] == 1
                    core.targets[-1] = target("tg-one", plugin="telegram", enabled=False)
                    core.revision += 1
                    await bridge.refresh_config()
                    checkpoints.put(
                        "tg-local", "tg-one", {"channel_avatar": {**avatar, "sha256": "changed"}}
                    )
                    calls = len(core.requests)
                    await bridge.publish_avatars(asyncio.Event())
                    assert len(core.requests) == calls
                finally:
                    await bridge.close()

    asyncio.run(run())
