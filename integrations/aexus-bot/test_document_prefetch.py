"""Opt-in server prefetch, shared request identity and durable restart/retry behavior."""
import asyncio
import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from channel_content import ChannelContentStore
from channel_documents import ChannelDocumentRequests


class DocumentPrefetchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aexus-prefetch-")
        self.root = Path(self.temp.name)
        self.store = ChannelContentStore(self.root / "store")
        self.calls = []
        self.gate = None
        self.fail = False
        self.payload = b"%PDF-offline-magazine\n" * 20
        parent = self

        class Transport:
            async def fetch_document(self, target, identifier, **kwargs):
                parent.calls.append(identifier)
                return 7, NS(id=identifier)

            async def download_document(self, message, *, directory, **kwargs):
                if parent.gate is not None:
                    await parent.gate.wait()
                if parent.fail:
                    raise OSError("temporary network error")
                directory.mkdir(parents=True, exist_ok=True)
                file = directory / (str(message.id)+".part")
                file.write_bytes(parent.payload)
                return NS(data=file)

        self.target = NS(id="magazines", enabled=True, options={"prefetch_documents": True})
        self.source = NS(id="tg", plugin="telegram", enabled=True, targets=[self.target])
        self.scheduler = NS(snapshot=NS(sources=NS(sources=[self.source])), plugins={"tg": NS(transport=Transport())})
        self.publisher = NS(targets={"tg": NS(sourceId="ns_magazines", plugin="telegram", targetId="magazines", enabled=True)})
        self.requests = ChannelDocumentRequests(self.store, self.scheduler, self.publisher)

    async def asyncTearDown(self):
        await self.requests.close()
        self.store.close()
        self.temp.cleanup()

    def post(self, identifier, stamp, source="ns_magazines"):
        file = {"id": "file", "name": identifier+".pdf", "mimeType": "application/pdf", "bytes": len(self.payload), "deferred": True}
        post = {"id": identifier, "source_id": source, "external_id": str(stamp), "published_at": stamp, "saved_at": None, "body": "original", "remote_files": json.dumps([file])}
        self.store.execute("write", {"changes": [{"table": "posts", "key": identifier, "row": post}]})
        return post

    async def settled(self):
        await asyncio.gather(*list(self.requests.tasks.values()))
        await asyncio.sleep(0)

    async def test_prefetch_also_warms_new_collection_before_core_publication(self):
        from frontier import telegram_target_options
        normal = telegram_target_options({"collect_timeout_seconds": 900})
        self.assertTrue(normal["document_metadata_only"])
        eager = telegram_target_options({"prefetch_documents": True, "collect_timeout_seconds": 900})
        self.assertFalse(eager["document_metadata_only"])
        self.assertTrue(eager["prefetch_documents"])
        self.assertEqual(eager["collect_timeout_seconds"], 900)

    async def test_target_policy_is_validated_by_the_real_plugin_contract(self):
        import yaml
        from xhs_local.plugins.registry import validate_options
        from xhs_local.plugins.contracts import PluginTarget, PluginContractError
        from xhs_local.plugins.sources.telegram.plugin import TelegramSourcePlugin
        root = Path(os.environ.get("AEXUS_XHS_ROOT", Path(__file__).resolve().parents[2]))
        schema = yaml.safe_load((root / "src/xhs_local/plugins/sources/telegram/manifest.yaml").read_text())["target_options"]
        options = validate_options({"prefetch_documents": True}, schema, label="target")
        TelegramSourcePlugin.validate_target(PluginTarget("magazines", "example_magazines", "Magazines", options))
        with self.assertRaises(PluginContractError):
            validate_options({"prefetch_documents": "yes"}, schema, label="target")

    async def test_only_opted_in_source_latest_first_without_automatic_pins(self):
        self.post("old", 1);self.post("new", 2);self.post("other", 3, "ns_other")
        self.assertEqual(await self.requests.prefetch_once(), 1)
        await self.settled()
        self.assertEqual(self.calls, [2])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM pins").fetchone()[0], 0)
        await self.requests.prefetch_once();await self.settled()
        self.assertEqual(self.calls, [2, 1])
        self.assertEqual(await self.requests.prefetch_once(), 0)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM document_requests WHERE state='completed'").fetchone()[0], 2)
        await self.requests.handle("document-prepare", {"postId": "new", "fileId": "file"})
        self.assertEqual(self.calls, [2, 1], "a user download reuses the server copy")
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM pins").fetchone()[0], 1)

    async def test_user_request_joins_inflight_auto_download_and_retains_it(self):
        self.post("new", 2);self.gate = asyncio.Event()
        await self.requests.prefetch_once();await asyncio.sleep(0)
        job = await self.requests.handle("document-prepare", {"postId": "new", "fileId": "file"})
        self.assertEqual(len(self.requests.tasks), 1)
        self.gate.set();await self.settled()
        self.assertEqual(self.requests.status(job["id"])["state"], "completed")
        self.assertEqual(self.calls, [2])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM pins").fetchone()[0], 1)

    async def test_failure_has_backoff_and_restart_recovers_pending_work(self):
        self.post("new", 2);self.fail = True
        await self.requests.prefetch_once();await self.settled()
        self.assertEqual(await self.requests.prefetch_once(), 0)
        self.assertEqual(self.calls, [2])
        with self.store.db:
            self.store.db.execute("UPDATE document_requests SET updated_at=?", (time.time()-301,))
        self.fail = False;self.gate = asyncio.Event()
        await self.requests.prefetch_once();await asyncio.sleep(0)
        await self.requests.close()
        self.requests = ChannelDocumentRequests(self.store, self.scheduler, self.publisher)
        self.gate.set();await self.requests.prefetch_once();await self.settled()
        self.assertEqual(self.store.db.execute("SELECT state FROM document_requests").fetchone()[0], "completed")

    async def test_metadata_updates_survive_download_and_policy_can_be_disabled(self):
        self.post("new", 2);self.target.options["prefetch_documents"] = False
        self.assertEqual(await self.requests.prefetch_once(), 0)
        self.target.options["prefetch_documents"] = True;self.gate = asyncio.Event()
        await self.requests.prefetch_once();await asyncio.sleep(0)
        post = self.post("new", 2);post["body"] = "updated while downloading"
        self.store.execute("write", {"changes": [{"table": "posts", "key": "new", "row": post}]})
        self.gate.set();await self.settled()
        value = json.loads(self.store.db.execute("SELECT data FROM content WHERE item_key='new'").fetchone()[0])
        self.assertEqual(value["body"], "updated while downloading")
        file = json.loads(value["remote_files"])[0]
        self.assertEqual(file["sha256"], hashlib.sha256(self.payload).hexdigest())
        self.assertEqual((self.store.root / file["serverPath"]).read_bytes(), self.payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
