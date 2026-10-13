from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from aiohttp.test_utils import TestClient, TestServer

from xhs_local.core.contracts import PublishResult, SourceRecord
from xhs_local.plugins.sinks.xiaohongshu.http import ManualPublicationAPI
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.schema import open_database
from xhs_local.website import create_website


class Renderer:
    def __init__(self, root):
        self.root, self.cards = root, []

    async def generate_news_cards(self, cards, **kwargs):
        self.cards = cards
        path = self.root / "rendered.png"
        path.write_bytes(b"image")
        return [path for _ in cards]


class Publisher:
    def __init__(self, *, ambiguous=False):
        self.notes = []
        self.ambiguous = ambiguous
        self.found = None

    async def publish(self, note):
        self.notes.append(note)
        return PublishResult(not self.ambiguous, not self.ambiguous, True)

    async def probe_submission(self, **kwargs):
        return {"found": self.found}

    async def close(self):
        pass


def setup(tmp_path, database, *, ambiguous=False):
    records = RecordsRepository(database, tmp_path)
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets/operator-api.token").write_text("operator-fixture")
    now = datetime.now(UTC)
    for plugin in ("telegram", "x", "youtube"):
        records.upsert(
            SourceRecord(
                plugin,
                "source",
                "target",
                plugin,
                plugin,
                "tech_news",
                now,
                now,
                "原始科技资料",
                "作者",
            )
        )
    publisher, renderer = Publisher(ambiguous=ambiguous), Renderer(tmp_path)
    api = ManualPublicationAPI(records, publisher=publisher, renderer=renderer)
    draft = {
        "request_id": "topic-one",
        "reviewed": True,
        "title": "相关技术进展",
        "body": "三个来源共同报道相关技术进展。",
        "topics": ["科技"],
        "items": [
            {"record_id": p, "headline": "技术进展", "text": "Agent 审核并撰写的具体信息。"}
            for p in ("telegram", "x", "youtube")
        ],
    }
    return records, publisher, renderer, api, draft


def test_only_reviewed_authenticated_requests_publish_mixed_sources_once(tmp_path):
    async def run():
        with open_database(tmp_path / "db.sqlite3", apply_migrations=True) as db:
            records, publisher, renderer, api, draft = setup(tmp_path, db)
            async with TestClient(
                TestServer(create_website(records, publication_api=api))
            ) as client:
                assert (await client.post("/api/xiaohongshu/publish", json=draft)).status == 401
                headers = {"Authorization": "Bearer operator-fixture"}
                assert (
                    await client.post(
                        "/api/xiaohongshu/publish",
                        json={**draft, "reviewed": False},
                        headers=headers,
                    )
                ).status == 400
                for _ in range(2):
                    response = await client.post(
                        "/api/xiaohongshu/publish", json=draft, headers=headers
                    )
                    assert response.status == 200
                    assert (await response.json())["state"] == "SUCCEEDED"
                assert len(publisher.notes) == 1
                assert {c["source_platform"] for c in renderer.cards} == {
                    "telegram",
                    "x",
                    "youtube",
                }
                assert publisher.notes[0].body == draft["body"]
                conflict = await client.post(
                    "/api/xiaohongshu/publish", json={**draft, "body": "changed"}, headers=headers
                )
                assert conflict.status == 409 and len(publisher.notes) == 1

    asyncio.run(run())


def test_ambiguous_request_is_reconciled_without_republication(tmp_path):
    async def run():
        with open_database(tmp_path / "db.sqlite3", apply_migrations=True) as db:
            records, publisher, _, api, draft = setup(tmp_path, db, ambiguous=True)
            async with TestClient(
                TestServer(create_website(records, publication_api=api))
            ) as client:
                headers = {"Authorization": "Bearer operator-fixture"}
                response = await client.post(
                    "/api/xiaohongshu/publish", json=draft, headers=headers
                )
                assert response.status == 202
                assert (await response.json())["state"] == "AMBIGUOUS"
                assert (
                    await client.post("/api/xiaohongshu/publish", json=draft, headers=headers)
                ).status == 202
                url = "/api/xiaohongshu/publications/topic-one"
                assert (await client.get(url, headers=headers)).status == 202
                publisher.found = True
                response = await client.get(url, headers=headers)
                assert (await response.json())["state"] == "SUCCEEDED"
                assert len(publisher.notes) == 1

    asyncio.run(run())


def test_missing_or_expired_sources_never_reach_publisher(tmp_path):
    async def run():
        with open_database(tmp_path / "db.sqlite3", apply_migrations=True) as db:
            records, publisher, _, api, draft = setup(tmp_path, db)
            old = records.get("x").record
            from dataclasses import replace

            records.upsert(replace(old, occurred_at=datetime.now(UTC) - timedelta(days=3)))
            async with TestClient(
                TestServer(create_website(records, publication_api=api))
            ) as client:
                response = await client.post(
                    "/api/xiaohongshu/publish",
                    json=draft,
                    headers={"Authorization": "Bearer operator-fixture"},
                )
                assert response.status == 400 and publisher.notes == []

    asyncio.run(run())
