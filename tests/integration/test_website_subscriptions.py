from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from aiohttp.test_utils import TestClient, TestServer

from xhs_local.configuration.loader import load_snapshot, snapshot_data
from xhs_local.configuration.subscriptions import parse_creator_link
from xhs_local.core.contracts import CollectBatch, SourceRecord
from xhs_local.pipeline.source_scheduler import SourceScheduler
from xhs_local.plugins.registry import SourcePluginRegistry
from xhs_local.storage.checkpoints import CheckpointRepository
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.schema import open_database
from xhs_local.website import WebsiteCollector, WebsiteSubscriptions, create_website


@pytest.mark.parametrize(
    "url,platform,locator",
    [
        ("https://x.com/Example?lang=en", "x", "Example"),
        ("twitter.com/Example/", "x", "Example"),
        (
            "https://www.youtube.com/@Example/videos?view=0",
            "youtube",
            "https://www.youtube.com/@Example",
        ),
        (
            "https://m.youtube.com/channel/UCexample/about",
            "youtube",
            "https://www.youtube.com/channel/UCexample",
        ),
    ],
)
def test_creator_link_normalization(url, platform, locator):
    found, target = parse_creator_link(url)
    assert found == platform and target.locator == locator


@pytest.mark.parametrize(
    "url",
    [
        "https://x.com/Example/status/123",
        "https://x.com/home",
        "https://x.com/too_long_a_handle",
        "https://youtube.com/watch?v=abc",
        "https://youtu.be/abc",
        "https://youtube.com/shorts/abc",
        "https://evil.example/@name",
        "https://x.com.evil.example/name",
        "file:///home/djf/config",
    ],
)
def test_only_supported_creator_homepages_are_accepted(url):
    with pytest.raises(ValueError):
        parse_creator_link(url)


class SleepingPlugin:
    async def collect(self, _request):
        await asyncio.Event().wait()

    async def close(self):
        pass


class OfflineRegistry(SourcePluginRegistry):
    def create(self, _prepared, **_dependencies):
        return SleepingPlugin()


def make_config(tmp_path):
    data = snapshot_data(load_snapshot(Path(__file__).resolve().parents[2] / "config"))
    data["app"]["agents"]["enabled"] = False  # This fixture exercises standalone website ownership.
    data["sources"]["sources"] = [
        {
            **s,
            "options": {} if s["plugin"] == "youtube" else s["options"],
            "targets": [
                {"id": "x-example", "locator": "Example", "name": "Example", "enabled": True},
                {"id": "x-peer", "locator": "Peer", "name": "Peer", "enabled": True},
            ]
            if s["plugin"] == "x"
            else [
                {
                    "id": "youtube-example",
                    "locator": "https://www.youtube.com/@Example",
                    "name": "Example",
                    "enabled": True,
                },
            ],
        }
        for s in data["sources"]["sources"]
        if s["plugin"] in {"x", "youtube"}
    ]
    config = tmp_path / "config"
    config.mkdir()
    for key, value in data.items():
        (config / f"{key}.yaml").write_text(yaml.safe_dump(value, sort_keys=False))
    return load_snapshot(config)


async def on_batch(*_args):
    pass


def make_record(key, source, target, platform):
    now = datetime.now(UTC)
    return SourceRecord(
        record_id=key,
        source_id=source,
        target_id=target,
        plugin_id=platform,
        external_id=key,
        content_type="tech_news",
        occurred_at=now,
        observed_at=now,
        text="收藏保留，取消关注停止采集",
        source_name="Example",
    )


def test_subscriptions_apply_live_persist_and_preserve_saved_posts(tmp_path):
    async def run():
        snapshot = make_config(tmp_path)
        with open_database(snapshot.database_path, apply_migrations=True) as db:
            records = RecordsRepository(db, snapshot.runtime_root)
            collector = WebsiteCollector(records, datetime(1970, 1, 1, tzinfo=UTC))
            scheduler = SourceScheduler(
                snapshot, OfflineRegistry(), CheckpointRepository(db), collector, on_batch
            )
            subscriptions = WebsiteSubscriptions(scheduler, records)
            await scheduler.start()
            try:
                original = dict(scheduler.tasks)
                ordinary = make_record("ordinary", "x-main", "x-example", "x")
                saved = replace(ordinary, record_id="saved", external_id="saved")
                youtube = make_record("video", "youtube", "youtube-example", "youtube")
                telegram = make_record("telegram", "telegram-main", "tg", "telegram")
                for record in (ordinary, saved, youtube, telegram):
                    records.upsert(record)
                records.set_news_favorite("saved", True)
                async with TestClient(TestServer(create_website(records, subscriptions))) as client:
                    response = await client.delete("/api/news/ordinary/author")
                    assert response.status == 200 and (await response.json())["removed"] == 1
                    assert "x-example" not in scheduler.tasks
                    assert original["x-example"].cancelled()
                    assert scheduler.tasks["x-peer"] is original["x-peer"]
                    assert scheduler.tasks["youtube-example"] is original["youtube-example"]
                    assert records.get("ordinary") is None and records.get("saved") is not None
                    feed = await (await client.get("/api/news?favorites=1")).json()
                    assert feed["items"][0]["following"] is False
                    # Even an already-running collector cannot reinsert after unfollowing.
                    result = await collector.commit(
                        CollectBatch("x-main", "x-example", (ordinary,), {}), config_revision="old"
                    )
                    assert not result.inserted_record_ids and records.get("ordinary") is None
                    persisted = load_snapshot(snapshot.config_root)
                    assert not next(
                        t
                        for s in persisted.sources.sources
                        for t in s.targets
                        if t.id == "x-example"
                    ).enabled
                    restarted = WebsiteCollector(records, datetime(1970, 1, 1, tzinfo=UTC))
                    restarted.set_sources(persisted)
                    assert ("x-main", "x-example") not in restarted.targets

                    response = await client.post(
                        "/api/subscriptions",
                        json={
                            "links": [
                                "https://twitter.com/example",
                                "https://x.com/NewCreator",
                                "https://x.com/newcreator",
                                "https://youtube.com/@NewChannel/videos",
                            ]
                        },
                    )
                    assert response.status == 200
                    assert [r["status"] for r in (await response.json())["results"]] == [
                        "restored",
                        "added",
                        "existing",
                        "added",
                    ]
                    assert {
                        "x-example",
                        "x-newcreator",
                        "youtube-newchannel",
                    } <= scheduler.tasks.keys()
                    assert scheduler.tasks["x-peer"] is original["x-peer"]
                    assert (
                        load_snapshot(snapshot.config_root).revision == scheduler.snapshot.revision
                    )
                    assert (await client.delete("/api/news/video/author")).status == 200
                    assert "youtube-example" not in scheduler.tasks
                    assert records.get("video") is None
                    assert (await client.delete("/api/news/telegram/author")).status == 400
                    assert records.get("telegram") is not None
                    before = (snapshot.config_root / "sources.yaml").read_bytes()
                    response = await client.post(
                        "/api/subscriptions",
                        json={
                            "links": [
                                "https://x.com/Valid",
                                "https://youtube.com/watch?v=abc",
                            ]
                        },
                    )
                    assert response.status == 400
                    assert (snapshot.config_root / "sources.yaml").read_bytes() == before
                    assert "x-valid" not in scheduler.tasks
                    assert (
                        await client.post("/api/subscriptions", json={"links": []})
                    ).status == 400
                    assert (await client.post("/api/subscriptions", data="{}")).status == 415
            finally:
                await scheduler.stop()

    asyncio.run(run())
