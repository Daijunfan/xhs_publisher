"""Offline server retention/assets and explicit document caching acceptance."""
import asyncio
import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from channel_content import ChannelContentStore, WEEK_MS
from channel_documents import ChannelDocumentRequests


class ChannelContentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aexus-channel-content-")
        self.root = Path(self.temp.name)
        self.store = ChannelContentStore(self.root / "store", self.root / "originals")

    async def asyncTearDown(self):
        self.store.close()
        self.temp.cleanup()

    async def test_archive_keeps_old_and_saved_messages(self):
        now = int(time.time() * 1000)
        changes = []
        for identifier, age, saved in [("new", WEEK_MS-1000, None), ("old", WEEK_MS+1000, None), ("saved", WEEK_MS+1000, now)]:
            changes.append({"table": "posts", "key": identifier, "row": {"id": identifier, "source_id": "ns_tg", "external_id": "123", "published_at": now-age, "saved_at": saved, "remote_files": "[]"}})
        self.store.execute("write", {"changes": changes})
        result = self.store.execute("snapshot", {})
        self.assertEqual({r["row"]["id"] for r in result["rows"]}, {"new", "old", "saved"})

    async def test_existing_server_image_import_verifies_hash(self):
        data = b"fixture image"
        digest = hashlib.sha256(data).hexdigest()
        file = self.store.source_media / digest[:2] / digest
        file.parent.mkdir(parents=True)
        file.write_bytes(data)
        result = self.store.execute("assets-import", {"assets": [{"id": "image", "sha256": digest, "bytes": len(data), "mimeType": "image/png"}]})
        self.assertEqual(result["missing"], [])
        self.assertEqual(self.store.execute("asset-info", {"id": "image"})["sha256"], digest)
        self.assertTrue(file.exists(), "import must not move/remove the original server file")
        self.store._expire()
        self.assertEqual(self.store.execute("assets-verify", {"ids": ["image"]})["failed"], [], "fresh imports survive GC until their metadata batch arrives")

    async def test_saved_post_keeps_images_after_default_week(self):
        now = int(time.time() * 1000)
        post = {"id": "saved", "source_id": "author", "published_at": now-WEEK_MS-1000, "saved_at": now}
        rows = [("posts", "saved", post), ("media", "picture", {"id": "picture", "post_id": "saved", "created_at": now-WEEK_MS-1000}), ("source_avatars", "author", {"source_id": "author", "updated_at": now-WEEK_MS-1000})]
        self.store.execute("write", {"changes": [{"table": table, "key": key, "row": row} for table, key, row in rows]})
        self.assertEqual(len(self.store.execute("snapshot", {})["rows"]), 3)
        post["saved_at"] = None
        self.store.execute("write", {"changes": [{"table": "posts", "key": "saved", "row": post}]})
        self.assertEqual(len(self.store.execute("snapshot", {})["rows"]), 3)

    async def test_document_list_does_not_fetch_then_one_requested_download(self):
        payload = b"%PDF-fixture-original\n" * 400
        document = {"id": "tg-123-456", "name": "Magazine.pdf", "mimeType": "application/pdf", "bytes": len(payload), "deferred": True}
        post = {"id": "np_doc", "source_id": "ns_tg", "external_id": "123", "published_at": int(time.time()*1000), "saved_at": None, "remote_files": json.dumps([document])}
        self.store.execute("write", {"changes": [{"table": "posts", "key": post["id"], "row": post}]})
        calls = []

        class Transport:
            async def fetch_document(self, target, identifier, **kwargs):
                calls.append("fetch")
                return 7, SimpleNamespace(id=identifier, document=SimpleNamespace(id=456))

            async def download_document(self, message, *, directory, **kwargs):
                calls.append("download")
                directory.mkdir(parents=True, exist_ok=True)
                file = directory / "fixture.part"
                file.write_bytes(payload)
                return SimpleNamespace(data=file)

        target = SimpleNamespace(id="tg-target", locator="@fixture")
        source = SimpleNamespace(id="tg-source", plugin="telegram", targets=[target])
        scheduler = SimpleNamespace(snapshot=SimpleNamespace(sources=SimpleNamespace(sources=[source])), plugins={source.id: SimpleNamespace(transport=Transport())})
        publisher = SimpleNamespace(targets={"tg": SimpleNamespace(sourceId="ns_tg", plugin="telegram", targetId=target.id)})
        requests = ChannelDocumentRequests(self.store, scheduler, publisher)
        try:
            self.store.execute("snapshot", {})
            self.assertEqual(calls, [])
            self.assertEqual(list((self.store.root/"documents").iterdir()), [])
            job = await requests.handle("document-prepare", {"postId": post["id"], "fileId": document["id"]})
            for _ in range(100):
                await asyncio.sleep(.01)
                result = requests.status(job["id"])
                if result["state"] not in {"queued", "running"}:
                    break
            self.assertEqual(result["state"], "completed", result)
            self.assertEqual(result["sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual((self.store.root/result["serverPath"]).read_bytes(), payload)
            await requests.handle("document-prepare", {"postId": post["id"], "fileId": document["id"]})
            self.assertEqual(calls, ["fetch", "download"], "a second click reuses the retained server copy")
        finally:
            await requests.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
