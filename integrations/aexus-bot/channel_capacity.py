"""Constant-time platform accounting; pressure evicts oldest unpinned messages."""
import json
from channel_queries import PLATFORM_BYTES


class ArchiveCapacity:
    def __init__(self, store):
        self.store, self.db, self.capacity_bytes = store, store.db, PLATFORM_BYTES
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS storage_objects(id TEXT PRIMARY KEY,platform TEXT NOT NULL,bytes INTEGER NOT NULL,post_id TEXT);
        CREATE INDEX IF NOT EXISTS storage_post ON storage_objects(post_id);
        CREATE TABLE IF NOT EXISTS platform_usage(platform TEXT PRIMARY KEY,bytes INTEGER NOT NULL);
        """)
        for event, values in [("INSERT", [("NEW", 1)]), ("DELETE", [("OLD", -1)]), ("UPDATE", [("OLD", -1), ("NEW", 1)])]:
            statements = [f"INSERT INTO platform_usage VALUES({name}.platform,{sign}*{name}.bytes) ON CONFLICT(platform) DO UPDATE SET bytes=bytes+excluded.bytes;" for name, sign in values]
            self.db.execute(f"CREATE TRIGGER IF NOT EXISTS usage_{event} AFTER {event} ON storage_objects BEGIN {' '.join(statements)} END")

    def register(self, identifier, source_id, size, post_id=None):
        route = self.db.execute("SELECT platform FROM source_routes WHERE id=?", (source_id,)).fetchone()
        if route is not None:
            self.db.execute("INSERT INTO storage_objects VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET platform=excluded.platform,bytes=excluded.bytes,post_id=excluded.post_id", (identifier, route[0], size, post_id))

    def content(self, kind, key, row):
        if row is None:
            self.db.execute("DELETE FROM storage_objects WHERE id=?", (kind+":"+key,));return
        source_id = row.get("source_id")
        if source_id:
            self.register(kind+":"+key, source_id, len(json.dumps(row, ensure_ascii=False).encode()), row.get("post_id", row.get("id") if kind=="posts" else None))
        if kind == "media":
            asset = self.db.execute("SELECT bytes FROM assets WHERE id=?", (key,)).fetchone()
            if asset: self.register("asset:"+key, source_id, asset[0], row["post_id"])

    def initialize(self):
        if self.db.execute("SELECT 1 FROM archive_metadata WHERE key='capacity_indexed'").fetchone(): return
        with self.db:
            for kind, key, raw in self.db.execute("SELECT kind,item_key,data FROM content").fetchall():
                self.content(kind, key, json.loads(raw))
            self.db.execute("INSERT INTO archive_metadata VALUES('capacity_indexed','1')")

    def usage(self):
        values = dict(self.db.execute("SELECT platform,bytes FROM platform_usage"))
        return {platform:{"capacityBytes":self.capacity_bytes,"usedBytes":max(0,values.get(platform,0))} for platform in ("telegram","x","youtube")}

    def enforce(self):
        evicted = []
        for platform, usage in self.usage().items():
            remaining = usage["usedBytes"] - usage["capacityBytes"]
            if remaining <= 0: continue
            candidates = self.db.execute("SELECT p.id FROM post_index p WHERE p.platform=? AND p.saved=0 AND p.state='active' AND NOT EXISTS(SELECT 1 FROM pins WHERE kind='posts' AND item_key=p.id) ORDER BY p.published_at,p.id", (platform,))
            for (identifier,) in candidates:
                amount = self.db.execute("SELECT COALESCE(SUM(bytes),0) FROM storage_objects WHERE post_id=?", (identifier,)).fetchone()[0]
                assets = self.db.execute("SELECT a.* FROM assets a JOIN content c ON c.kind='media' AND c.item_key=a.id WHERE json_extract(c.data,'$.post_id')=?", (identifier,)).fetchall()
                for asset in assets:
                    (self.store.root / "assets" / asset["file"]).unlink(missing_ok=True)
                    for preview in (self.store.root / "previews").glob(asset["file"]+"-*.webp"): preview.unlink()
                    self.db.execute("DELETE FROM assets WHERE id=?", (asset["id"],))
                self.db.execute("DELETE FROM content WHERE kind='media' AND json_extract(data,'$.post_id')=?", (identifier,))
                self.db.execute("DELETE FROM content WHERE kind='posts' AND item_key=?", (identifier,))
                self.db.execute("DELETE FROM post_index WHERE id=?", (identifier,))
                self.db.execute("DELETE FROM storage_objects WHERE post_id=?", (identifier,)); remaining -= amount
                evicted.append(identifier)
                if remaining <= 0: break
            if remaining > 0: raise ValueError(platform+" storage is full of saved/downloaded content")
        return evicted

