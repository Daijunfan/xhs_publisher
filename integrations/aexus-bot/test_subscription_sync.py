"""Run with the existing Xhs venv/PYTHONPATH. Temporary database, no network/model calls."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from xhs_local.pipeline.agents import CollectorRequestError
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.schema import open_database
from subscription_sync import CorePublisher


class SubscriptionSyncTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aexus-subscription-test-")
        self.root = Path(self.temp.name)
        self.database = open_database(self.root / "test.sqlite3", apply_migrations=True)
        records = RecordsRepository(self.database, self.root)
        snapshot = SimpleNamespace(
            app=SimpleNamespace(agents=SimpleNamespace(endpoint="http://127.0.0.1:1", token_file="test.token", poll_seconds=.02)),
            sources=SimpleNamespace(sources=[]), resolve=lambda name: self.root / name,
        )
        self.version = 1
        self.events = []
        self.status = []
        self.applied = []
        self.fail_apply = False
        self.fail_ack = False
        self.confirmed = asyncio.Event()

        async def apply(targets):
            self.events.append(("apply", self.version))
            if self.fail_apply:
                raise ValueError("scheduler rejected configuration")
            self.applied.append((self.version, targets))

        self.publisher = CorePublisher(snapshot, records, apply, lambda **fields: self.status.append(fields))

        async def call(command, args):
            if command == "channel.collector-config":
                changed = args.get("sinceRevision") != self.version
                return {"revision": self.version, "changed": changed, **({"targets": [{"sourceId": "ns_alpha", "targetId": "youtube-alpha", "plugin": "youtube", "locator": "https://www.youtube.com/@fixturealpha", "name": "Alpha", "enabled": True, "pollSeconds": 7200}]} if changed else {})}
            self.assertEqual(command, "channel.collector-ack")
            self.assertEqual(self.applied[-1][0], args["revision"], "receipt must follow scheduler application")
            self.events.append(("ack", args["revision"]))
            if self.fail_ack:
                self.fail_ack = False
                raise CollectorRequestError("temporary receipt failure")
            if args["revision"] == 2:
                self.confirmed.set()
            return {"revision": args["revision"], "appliedAt": 123}

        self.publisher._call = call

    async def asyncTearDown(self):
        await self.publisher.close()
        self.database.close()
        self.temp.cleanup()

    async def test_receipt_after_apply_and_checkpoint(self):
        await self.publisher.refresh_config()
        self.assertEqual(self.events, [("apply", 1), ("ack", 1)])
        self.assertEqual(self.publisher.checkpoints.get("agents-company", "config")["revision"], 1)
        self.assertEqual(self.status[-1]["agents"]["applied_revision"], 1)

    async def test_failed_application_never_acknowledges(self):
        await self.publisher.refresh_config()
        self.version = 2
        self.fail_apply = True
        with self.assertRaises(ValueError):
            await self.publisher.refresh_config()
        self.assertNotIn(("ack", 2), self.events)
        self.assertEqual(self.publisher.checkpoints.get("agents-company", "config")["revision"], 1)

    async def test_failed_receipt_retries_without_reapplying(self):
        self.fail_ack = True
        with self.assertRaises(CollectorRequestError):
            await self.publisher.refresh_config()
        await self.publisher.refresh_config()
        self.assertEqual(self.events, [("apply", 1), ("ack", 1), ("ack", 1)])
        self.assertEqual(len(self.applied), 1)

    async def test_management_updates_during_blocked_publication(self):
        blocked = asyncio.Event()
        entered = asyncio.Event()

        async def slow_publication(stop):
            entered.set()
            await blocked.wait()

        self.publisher.publish_avatars = slow_publication
        stop = asyncio.Event()
        sending = asyncio.create_task(self.publisher.run(stop))
        watching = asyncio.create_task(self.publisher.watch_subscriptions(stop))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            self.version = 2
            await asyncio.wait_for(self.confirmed.wait(), 1)
            self.assertFalse(sending.done())
            self.assertIn(("ack", 2), self.events)
        finally:
            stop.set()
            for task in (sending, watching):
                task.cancel()
            await asyncio.gather(sending, watching, return_exceptions=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
