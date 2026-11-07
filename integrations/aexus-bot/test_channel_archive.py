import json
import asyncio
import base64
import tempfile
import time
import unittest
from pathlib import Path

from channel_content import ChannelContentStore


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ChannelContentStore(Path(self.temp.name))
        self.sources = [{"id": p, "plugin": p, "channel_id": p, "name": p} for p in ("x", "youtube", "telegram")]
        self.store.execute("configure", {"sources": self.sources})

    def tearDown(self):
        self.store.close();self.temp.cleanup()

    def post(self, identifier, platform, published, saved=None, received=None, body="Original text"):
        row = {"id": identifier, "source_id": platform, "state": "active", "published_at": published, "received_at": received if received is not None else published, "saved_at": saved, "title": identifier, "body": body, "media_ids": "[]", "remote_files": "[]"}
        self.store.execute("write", {"changes": [{"table": "posts", "key": identifier, "row": row}]})
        return row

    def test_no_age_expiry_and_independent_platform_capacity(self):
        now=int(time.time()*1000)
        self.post("old-x", "x", now-500*86400000)
        self.post("old-youtube", "youtube", now-500*86400000)
        self.assertEqual(self.store.execute("posts-page", {"sourceIds": ["x"]})["total"], 1)
        first=self.store.capacity_usage();self.assertEqual({x["capacityBytes"] for x in first.values()}, {1_000_000_000_000})
        self.store.capacity.capacity_bytes=first["x"]["usedBytes"]+30
        self.post("new-x", "x", now)
        self.assertEqual(self.store.execute("posts-page", {"sourceIds": ["x"]})["postIds"], ["new-x"])
        self.assertEqual(self.store.execute("posts-page", {"sourceIds": ["youtube"]})["postIds"], ["old-youtube"])

    def test_saved_and_downloaded_pins_survive_pressure(self):
        self.post("saved", "x", 1, saved=10)
        self.post("requested-download", "x", 2)
        self.store.execute("pin", {"table": "posts", "key": "requested-download", "saved": True})
        self.post("old-ordinary", "x", 3)
        self.store.capacity.capacity_bytes=self.store.capacity_usage()["x"]["usedBytes"]+10
        self.post("new", "x", 4)
        ids=self.store.execute("posts-page", {"sourceIds": ["x"]})["postIds"]
        self.assertIn("saved",ids);self.assertIn("requested-download",ids);self.assertNotIn("old-ordinary",ids)

    def test_read_mark_preserves_arrivals_after_request_and_never_rolls_back(self):
        self.post("old", "x", 1, received=10)
        self.post("arrived-during-request", "x", 2, received=110)
        result=self.store.execute("read-mark", {"all":True,"sourceIds":["x"],"readAt":100})
        self.assertEqual(result["marked"],1)
        states=self.store.execute("read-states", {"sourceIds":["x"],"ids":["old","arrived-during-request"]})["entries"]
        self.assertEqual([item["state"] for item in states],["read","unread"])
        self.assertEqual(self.store.execute("summaries",{})["sources"][0]["unread"],1)
        self.store.execute("read-mark", {"all":True,"sourceIds":["x"],"readAt":200})
        self.assertEqual(self.store.execute("read-mark", {"all":True,"sourceIds":["x"],"readAt":50})["marked"],0)
        self.assertEqual(self.store.execute("summaries",{})["sources"][0]["unread"],0)
        self.assertEqual(self.store.db.execute("SELECT received_before FROM source_read_marks WHERE source_id='x'").fetchone()[0],200)

    def test_watermark_read_counts_survive_updates_deletions_and_backfill(self):
        a=self.post("a","x",1,received=10);self.post("b","x",2,received=20)
        self.assertEqual(self.store.execute("read-mark", {"all":True,"sourceIds":["x"],"readAt":100})["marked"],2)
        self.assertEqual(self.store.execute("summaries",{})["sources"][0]["unread"],0)
        a["body"]="Updated";self.store.execute("write",{"changes":[{"table":"posts","key":"a","row":a}]})
        self.post("late-old-news","x",0,received=101)
        summary=next(s for s in self.store.execute("summaries",{})["sources"] if s["sourceId"]=="x")
        self.assertEqual(summary["unread"],1);self.assertEqual(summary["firstUnread"]["id"],"late-old-news")
        self.store.execute("write",{"changes":[{"table":"posts","key":"b","row":None}]})
        self.assertEqual(next(s for s in self.store.execute("summaries",{})["sources"] if s["sourceId"]=="x")["unread"],1)
        states=self.store.execute("read-states",{"ids":["a","late-old-news"],"sourceIds":["x"]})["entries"]
        self.assertEqual([x["state"] for x in states],["read","unread"])

    def test_indexed_literal_search_and_stable_refresh_pages(self):
        for i in range(40):self.post("p"+str(i),"x",i,received=i,body="中文搜索针 café %_" if i==2 else "Other content")
        self.assertEqual(self.store.execute("posts-page",{"sourceIds":["x"],"query":"搜索针"})["postIds"],["p2"])
        self.assertEqual(self.store.execute("posts-page",{"sourceIds":["x"],"query":"%_"})["postIds"],["p2"])
        args={"sourceIds":["x"],"order":"discovery","seed":"first","snapshot":100,"limit":8}
        first=self.store.execute("posts-page",args);second=self.store.execute("posts-page",{**args,"cursor":first["nextCursor"]})
        self.assertFalse(set(first["postIds"])&set(second["postIds"]))
        refreshed=self.store.execute("posts-page",{**args,"seed":"new","avoidFirst":first["postIds"][0]})
        self.assertNotEqual(first["postIds"][0],refreshed["postIds"][0])
        with self.assertRaises(ValueError):self.store.execute("posts-page",{**args,"seed":"foreign","cursor":first["nextCursor"]})


class AsyncAssetTests(unittest.IsolatedAsyncioTestCase):
    async def test_parallel_image_io_does_not_block_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            store=ChannelContentStore(Path(directory))
            try:
                store.execute('asset-put',{'id':'image','mimeType':'image/png','data':base64.b64encode(b'fixture image bytes').decode()})
                original=store._asset_payload
                def delayed(row,args):
                    time.sleep(.15);return original(row,args)
                store._asset_payload=delayed
                start=time.monotonic();tasks=[asyncio.create_task(store.execute_async('asset-read',{'id':'image'})) for _ in range(4)]
                await asyncio.sleep(.01)
                store.execute('summaries',{})
                self.assertLess(time.monotonic()-start,.12,'metadata must remain responsive during image decoding')
                values=await asyncio.gather(*tasks)
                self.assertEqual(len(values),4);self.assertLess(time.monotonic()-start,.45)
            finally:store.close()

if __name__ == "__main__":unittest.main(verbosity=2)
