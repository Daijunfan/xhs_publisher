from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta

import pytest
import yaml

from xhs_local.configuration.video_sources import (
    creator_target,
    import_creator_document,
    read_creator_document,
)
from xhs_local.core.errors import AuthenticationRequired, TransientError
from xhs_local.core.states import WorkTopic
from xhs_local.plugins.contracts import CollectRequest, PluginTarget, SourcePluginContext
from xhs_local.plugins.sources.video.client import run_command
from xhs_local.plugins.sources.youtube.client import recent_uploads
from xhs_local.plugins.sources.youtube.plugin import YouTubeSourcePlugin
from xhs_local.storage.checkpoints import CheckpointRepository
from xhs_local.storage.database import Database
from xhs_local.storage.schema import migrate


def test_all_creator_urls_load_and_credentials_never_enter_config(tmp_path):
    document = tmp_path / "creators.md"
    document.write_text(
        "Paraformer-v2\napikey:test-secret\n"
        + "\n".join(
            [
                "https://www.youtube.com/@AndrejKarpathy",
                "https://www.youtube.com/@AndrejKarpathy",
                "https://www.youtube.com/channel/UC4LoD4yNBuLKQwDOV6t-KPw",
                "https://www.youtube.com/ComputationsInFinance",
                "https://space.bilibili.com/1567748478",
            ]
        )
    )
    targets, key = read_creator_document(document)
    assert {platform: len(items) for platform, items in targets.items()} == {
        "youtube": 3,
    }
    assert key == "test-secret"
    config = tmp_path / "config"
    config.mkdir()
    (config / "app.yaml").write_text("runtime_root: ../runtime\n")
    original = (
        "version: 1\nsources:\n  - id: telegram\n"
        "    plugin: telegram\n    targets: [] # preserve me\n"
    )
    (config / "sources.yaml").write_text(original)
    counts = import_creator_document(document, config)
    imported = (config / "sources.yaml").read_text()
    assert imported.startswith(original)
    assert "test-secret" not in imported
    assert (tmp_path / "runtime/secrets/dashscope-api-key").stat().st_mode & 0o777 == 0o600
    assert counts == {"youtube": 3}
    (config / "sources.yaml").write_text(
        imported.replace("poll_seconds: 1800", "poll_seconds: 7200")
    )
    import_creator_document(document, config)
    sources = yaml.safe_load((config / "sources.yaml").read_text())["sources"]
    assert len(sources) == 2
    assert all(item["poll_seconds"] == 7200 for item in sources if item["plugin"] != "telegram")


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=abc",
        "https://www.bilibili.com/video/BV123",
        "https://youtu.be/abc",
    ],
)
def test_video_urls_are_not_creator_homepages(url):
    with pytest.raises(ValueError):
        creator_target(url)


def test_youtube_lazy_discovery_never_requests_pages_past_old_uploads():
    def entries():
        yield {"id": "new", "timestamp": 200}
        yield {"id": "old", "timestamp": 50}
        raise AssertionError("historical continuation must not be fetched")

    info = {"entries": [{"entries": entries()}, {"entries": [{"id": "short", "timestamp": 210}]}]}
    assert [entry["id"] for entry in recent_uploads(info, 100)] == ["new", "short"]


def test_activation_survives_restart_and_does_not_move_after_failed_poll(tmp_path):
    path = tmp_path / "app.sqlite3"
    for value in ("2026-09-12T00:00:00+00:00", "2026-09-13T00:00:00+00:00"):
        db = Database(path)
        migrate(db)
        result = CheckpointRepository(db).initialize(
            "videos", "__activation__", {"activated_at": value}
        )
        assert result["activated_at"] == "2026-09-12T00:00:00+00:00"
        db.close()


def test_failed_video_is_retried_after_cursor_advances_and_peers_are_committed(tmp_path):
    now = datetime.now(UTC)

    class Client:
        fail = True
        scans = []

        async def discover(self, homepage, since):
            self.scans.append(since)
            return (
                {
                    "entries": [
                        {"id": "retry", "timestamp": now.timestamp()},
                        {"id": "good", "timestamp": now.timestamp()},
                    ]
                }
                if self.fail
                else {"entries": []}
            )

        async def metadata(self, url):
            if url.endswith("retry") and self.fail:
                raise TimeoutError("offline")
            return {"timestamp": now.timestamp(), "title": "New technology"}

    client = Client()
    context = SourcePluginContext("youtube", tmp_path, {})
    target = PluginTarget("youtube-example", "https://www.youtube.com/@Example", "Example")
    activation = (now - timedelta(days=60)).isoformat()
    first = asyncio.run(
        YouTubeSourcePlugin(context, client=client).collect(
            CollectRequest("youtube", target, {"activated_at": activation}, now)
        )
    )
    assert [r.external_id for r in first.records] == ["good"]
    assert [entry["id"] for entry in first.checkpoint["pending_metadata"]] == ["retry"]
    client.fail = False
    second = asyncio.run(
        YouTubeSourcePlugin(context, client=client).collect(
            CollectRequest("youtube", target, first.checkpoint, now + timedelta(minutes=30))
        )
    )
    assert [r.external_id for r in second.records] == ["retry"]
    assert second.checkpoint["pending_metadata"] == []
    assert client.scans[1] == now - timedelta(days=1)
    assert second.checkpoint["activated_at"] == activation


def test_youtube_exact_time_excludes_a_pre_activation_video_despite_relative_date(tmp_path):
    now = datetime.now(UTC)

    class Client:
        async def discover(self, *args):
            return {"entries": [{"id": "old", "timestamp": now.timestamp()}]}

        async def metadata(self, url):
            return {"timestamp": (now - timedelta(seconds=10)).timestamp()}

    plugin = YouTubeSourcePlugin(SourcePluginContext("youtube", tmp_path, {}), client=Client())
    batch = asyncio.run(
        plugin.collect(
            CollectRequest(
                "youtube",
                PluginTarget("youtube-example", "https://www.youtube.com/@Example", "Example"),
                {"activated_at": now.isoformat()},
                now,
            )
        )
    )
    assert batch.records == ()
    assert batch.checkpoint["seen_video_ids"] == ["old"]


@pytest.mark.parametrize(
    "plugin_type,platform,url",
    [
        (YouTubeSourcePlugin, "youtube", "https://www.youtube.com/@Example"),
    ],
)
def test_discovery_saves_incremental_ids_and_uses_durable_video_queue(
    tmp_path, plugin_type, platform, url
):
    now = datetime.now(UTC)

    class Client:
        async def metadata(self, url):
            return {"timestamp": now.timestamp(), "title": "New video"}

        async def discover(self, homepage, activated_at):
            assert homepage == url
            return {
                "entries": [
                    {"id": "old", "timestamp": (now - timedelta(days=8)).timestamp()},
                    {"id": "new", "timestamp": now.timestamp(), "title": "New video"},
                ]
            }

    context = SourcePluginContext(platform, tmp_path, {})
    plugin = plugin_type(context, client=Client())
    target = PluginTarget(platform + "-example", url, "Example")
    request = CollectRequest(
        platform, target, {"activated_at": (now - timedelta(minutes=1)).isoformat()}, now
    )
    batch = asyncio.run(plugin.collect(request))
    assert [record.external_id for record in batch.records] == ["new"]
    assert batch.work_topic == WorkTopic.VIDEO_PREPARE
    assert batch.preserve_existing is True
    restarted = plugin_type(context, client=Client())
    second = asyncio.run(restarted.collect(CollectRequest(platform, target, batch.checkpoint, now)))
    assert second.records == ()


def test_incomplete_cached_metadata_is_fetched_again_until_timestamp_available(tmp_path):
    now = datetime.now(UTC)

    class Client:
        calls = []
        complete = False

        async def discover(self, *_args):
            return {"entries": []}

        async def metadata(self, url):
            self.calls.append(url)
            return {"timestamp": now.timestamp()} if self.complete else {"title": "Still missing"}

    client = Client()
    context = SourcePluginContext("youtube", tmp_path, {})
    target = PluginTarget("youtube-example", "https://www.youtube.com/@Example", "Example")
    checkpoint = {
        "activated_at": (now - timedelta(days=1)).isoformat(),
        "pending_metadata": [
            {"id": "broken", "video_metadata": {"title": "Cached", "timestamp": None}},
            {"id": "good-cache", "video_metadata": {"release_timestamp": now.timestamp()}},
        ],
    }
    first = asyncio.run(
        YouTubeSourcePlugin(context, client=client).collect(
            CollectRequest("youtube", target, checkpoint, now)
        )
    )
    assert client.calls == ["https://www.youtube.com/watch?v=broken"]
    assert [record.external_id for record in first.records] == ["good-cache"]
    assert first.errors == 1
    assert [entry["id"] for entry in first.checkpoint["pending_metadata"]] == ["broken"]

    client.complete = True
    second = asyncio.run(
        YouTubeSourcePlugin(context, client=client).collect(
            CollectRequest("youtube", target, first.checkpoint, now + timedelta(minutes=30))
        )
    )
    assert client.calls == ["https://www.youtube.com/watch?v=broken"] * 2
    assert [record.external_id for record in second.records] == ["broken"]
    assert second.records[0].payload["video_metadata"]["timestamp"] == now.timestamp()
    assert second.errors == 0 and second.checkpoint["pending_metadata"] == []


@pytest.mark.parametrize(
    "stderr,error_type,code",
    [
        (
            "The current session has been rate-limited by YouTube for up to an hour. "
            "https://example.test/?token=private-cookie-value",
            TransientError,
            "YOUTUBE_RATE_LIMITED",
        ),
        (
            "Your account has been rate-limited by YouTube for up to an hour. "
            "https://example.test/?token=private-cookie-value",
            TransientError,
            "YOUTUBE_RATE_LIMITED",
        ),
        (
            "Video unavailable https://example.test/?token=private-cookie-value",
            TransientError,
            None,
        ),
        (
            "Sign in to confirm https://example.test/?token=private-cookie-value",
            AuthenticationRequired,
            None,
        ),
    ],
)
def test_video_command_errors_are_classified_without_exposing_stderr(stderr, error_type, code):
    command = [sys.executable, "-c", "import sys;sys.stderr.write(sys.argv[1]);sys.exit(1)", stderr]
    with pytest.raises(error_type) as raised:
        asyncio.run(run_command(command))
    assert raised.value.code == code
    assert "https://" not in str(raised.value)
    assert "private-cookie-value" not in str(raised.value)
    if code:
        assert "one hour" in str(raised.value)


def test_video_command_success_preserves_output_bytes():
    assert asyncio.run(run_command([sys.executable, "-c", "print(123)"])) == b"123\n"
