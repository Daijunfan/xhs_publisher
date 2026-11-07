"""Run against the matching Frontier source; no network, accounts or production records."""
import asyncio
import tempfile
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from xhs_local.core.errors import AuthenticationRequired
from xhs_local.frontier.collector import FrontierScheduler
from xhs_local.pipeline.source_scheduler import SourceScheduler
from xhs_local.plugins.contracts import CollectRequest, PluginTarget, SourcePluginContext
from xhs_local.plugins.sources.youtube.client import recent_uploads
from xhs_local.plugins.sources.youtube.plugin import YouTubeSourcePlugin


class DiscoveryTests(unittest.TestCase):
    def test_flat_discovery_keeps_all_tabs_without_watch_requests(self):
        info = {"entries": [{"entries": [{"id": "video", "timestamp": 200}]},
                            {"entries": [{"id": "short"}]},
                            {"entries": [{"id": "live", "release_timestamp": 1,
                                          "live_status": "is_live"}, {"id": "new", "timestamp": 210}]}]}
        def forbidden(*args):
            self.fail("Flat discovery must not resolve watch metadata")
        rows = list(recent_uploads(info, 100, forbidden))
        self.assertEqual([row["id"] for row in rows], ["video", "short", "live", "new"])
        self.assertEqual(rows[2]["release_timestamp"], 1)

    def test_undated_pages_rotate_using_durable_known_ids(self):
        info = {"entries": [{"id": str(n)} for n in range(40)]}
        first = list(recent_uploads(info, 100))
        second = list(recent_uploads(info, 100, seen_video_ids={row["id"] for row in first}))
        self.assertEqual(len(first), 30)
        self.assertEqual([row["id"] for row in second], [str(n) for n in range(30, 40)])


class CollectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = datetime.now(UTC)
        self.context = SourcePluginContext("youtube", Path(self.temp.name), {})
        self.target = PluginTarget("youtube-example", "https://www.youtube.com/@Example", "Example")
        self.activation = (self.now - timedelta(days=1)).isoformat()

    async def asyncTearDown(self):
        self.temp.cleanup()

    async def collect(self, client, checkpoint=None, deadline=None):
        return await YouTubeSourcePlugin(self.context, client=client).collect(CollectRequest(
            "youtube", self.target, checkpoint or {"activated_at": self.activation}, self.now,
            deadline=deadline))

    async def test_auth_failure_commits_pending_and_rotates_without_marking_seen(self):
        now = self.now
        class Client:
            calls = []
            known = None
            async def discover(self, homepage, since, seen_video_ids=()):
                self.known = set(seen_video_ids)
                return {"entries": [{"id": "fresh", "timestamp": now.timestamp()}]}
            async def metadata(self, url):
                self.calls.append(url)
                raise AuthenticationRequired("session needs renewal")
        client = Client()
        checkpoint = {"activated_at": self.activation,
                      "pending_metadata": [{"id": str(n)} for n in range(100)]}
        batch = await self.collect(client, checkpoint)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.known, {str(n) for n in range(100)})
        self.assertEqual(len(batch.checkpoint["pending_metadata"]), 101)
        self.assertEqual(batch.checkpoint["pending_metadata"][-1]["id"], "fresh")
        self.assertEqual(batch.checkpoint["seen_video_ids"], [])
        self.assertEqual(batch.checkpoint["last_polled_at"], self.now.isoformat())

    async def test_low_budget_preserves_unprocessed_items_as_partial(self):
        class Client:
            async def discover(self, *args):
                return {"entries": [{"id": "a"}, {"id": "b"}]}
            async def metadata(self, url):
                raise AssertionError("Insufficient budget must not start a watch request")
        batch = await self.collect(Client(), deadline=time.monotonic() + 10)
        self.assertEqual([row["id"] for row in batch.checkpoint["pending_metadata"]], ["a", "b"])
        self.assertEqual(batch.checkpoint["seen_video_ids"], [])
        self.assertGreater(batch.errors, 0)

    async def test_new_items_precede_old_pending_and_keep_exact_publication_time(self):
        exact = self.now - timedelta(seconds=5)
        class Client:
            calls = []
            async def discover(self, *args):
                return {"entries": [{"id": "fresh", "timestamp": 2000000000}]}
            async def metadata(self, url):
                self.calls.append(url)
                return {"timestamp": exact.timestamp(), "title": "Metadata"}
        client = Client()
        batch = await self.collect(client, {"activated_at": self.activation,
                                           "pending_metadata": [{"id": "pending"}]})
        self.assertTrue(client.calls[0].endswith("fresh"))
        self.assertEqual(batch.records[0].payload["video_metadata"]["timestamp"], exact.timestamp())

    async def test_pending_live_stream_is_refreshed_after_it_finishes(self):
        exact = self.now - timedelta(seconds=5)
        class Client:
            calls = 0
            async def discover(self, homepage, since, seen_video_ids=()):
                assert set(seen_video_ids) == {"live"}
                return {"entries": []}
            async def metadata(self, url):
                self.calls += 1
                return {"timestamp": exact.timestamp(), "live_status": "was_live"}
        client = Client()
        batch = await self.collect(client, {"activated_at": self.activation, "pending_metadata": [
            {"id": "live", "live_status": "is_upcoming", "video_metadata": {
                "timestamp": (self.now + timedelta(hours=1)).timestamp(), "live_status": "is_upcoming"}}]})
        self.assertEqual(client.calls, 1)
        self.assertEqual([r.external_id for r in batch.records], ["live"])
        self.assertEqual(batch.checkpoint["pending_metadata"], [])


class SchedulingTests(unittest.IsolatedAsyncioTestCase):
    async def test_dynamic_targets_share_staggered_start_slots(self):
        scheduler = FrontierScheduler.__new__(FrontierScheduler)
        scheduler.next_starts = {}
        scheduler.status = {str(n): {"plugin_id": "youtube"} for n in range(4)}
        scheduler.stopping = False
        scheduler._status_now = lambda: datetime.now(UTC)
        scheduler._wait_until = AsyncMock()
        with patch.object(SourceScheduler, "_target_loop", new=AsyncMock()):
            for n in range(4):
                await scheduler._target_loop(None, None, SimpleNamespace(id=str(n)), 180,
                                             SimpleNamespace(cancelled=False))
        waits = [call.args[2] for call in scheduler._wait_until.call_args_list]
        self.assertEqual(len(waits), 3)
        self.assertTrue(all((b-a).total_seconds() > 7.9 for a, b in zip(waits, waits[1:])))


if __name__ == "__main__":
    unittest.main(verbosity=2)
