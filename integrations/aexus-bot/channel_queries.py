"""Indexed archive pages; no history or image blobs are sent during bootstrap."""
import base64
import hashlib
import json
import time

NO_EXPIRY = 9007199254740991
PLATFORM_BYTES = 1_000_000_000_000


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def cursor(value):
    return base64.urlsafe_b64encode(canonical(value).encode()).decode().rstrip("=")


def uncursor(value):
    try:
        return json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
    except (ValueError, TypeError) as error:
        raise ValueError("Invalid archive cursor") from error


class ArchiveQueries:
    def __init__(self, store):
        self.store, self.db, self.feeds = store, store.db, {}
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS source_routes(id TEXT PRIMARY KEY,platform TEXT NOT NULL,channel_id TEXT,name TEXT);
        CREATE TABLE IF NOT EXISTS read_state(id TEXT PRIMARY KEY,read_at INTEGER);
        CREATE TABLE IF NOT EXISTS source_read_marks(source_id TEXT PRIMARY KEY,received_before INTEGER NOT NULL,read_at INTEGER NOT NULL,skipped INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS post_index(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,published_at INTEGER NOT NULL,received_at INTEGER NOT NULL,state TEXT NOT NULL,saved INTEGER NOT NULL,unread INTEGER NOT NULL,title TEXT,has_media INTEGER NOT NULL,has_links INTEGER NOT NULL,platform TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS post_source_time ON post_index(source_id,state,published_at DESC,id DESC);
        CREATE INDEX IF NOT EXISTS post_time ON post_index(state,published_at DESC,id DESC);
        CREATE INDEX IF NOT EXISTS post_unread_time ON post_index(source_id,state,unread,published_at,id);
        CREATE INDEX IF NOT EXISTS post_unread_received ON post_index(source_id,state,unread,received_at,published_at,id);
        CREATE TABLE IF NOT EXISTS source_counts(source_id TEXT PRIMARY KEY,total INTEGER NOT NULL,saved INTEGER NOT NULL,unread INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS archive_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS content_parent ON content(kind,json_extract(data,'$.post_id'),item_key);
        CREATE INDEX IF NOT EXISTS content_message_channel ON content(kind,json_extract(data,'$.channel_id'),json_extract(data,'$.sequence'));
        CREATE VIRTUAL TABLE IF NOT EXISTS post_search USING fts5(id UNINDEXED,text,tokenize='trigram');
        CREATE TRIGGER IF NOT EXISTS post_search_delete AFTER DELETE ON post_index BEGIN DELETE FROM post_search WHERE rowid=OLD.rowid;END;
        """)
        if "platform" not in {r[1] for r in self.db.execute("PRAGMA table_info(post_index)")}:
            self.db.execute("ALTER TABLE post_index ADD COLUMN platform TEXT NOT NULL DEFAULT ''")
        self.db.execute("CREATE INDEX IF NOT EXISTS platform_oldest ON post_index(platform,state,saved,published_at,id)")
        self.db.execute("CREATE INDEX IF NOT EXISTS platform_time ON post_index(platform,state,published_at DESC,id DESC)")
        for event, rows in [("INSERT", [("NEW", 1)]), ("DELETE", [("OLD", -1)]), ("UPDATE", [("OLD", -1), ("NEW", 1)])]:
            statements = []
            for alias, sign in rows:
                statements.append(f"""INSERT INTO source_counts VALUES({alias}.source_id,{sign}*({alias}.state='active'),{sign}*({alias}.state='active')*{alias}.saved,{sign}*({alias}.state='active')*{alias}.unread)
                ON CONFLICT(source_id) DO UPDATE SET total=total+excluded.total,saved=saved+excluded.saved,unread=unread+excluded.unread;""")
                statements.append(f"UPDATE source_read_marks SET skipped=skipped+{sign}*({alias}.state='active')*{alias}.unread WHERE source_id={alias}.source_id AND {alias}.received_at<=received_before;")
            self.db.execute(f"DROP TRIGGER IF EXISTS post_counts_{event}")
            self.db.execute(f"CREATE TRIGGER post_counts_{event} AFTER {event} ON post_index BEGIN {' '.join(statements)} END")
        if self.db.execute("SELECT 1 FROM archive_metadata WHERE key='search_indexed'").fetchone() is None:
            with self.db:
                for (raw,) in self.db.execute("SELECT data FROM content WHERE kind='posts'").fetchall():
                    self.index(json.loads(raw))
                self.db.execute("INSERT OR REPLACE INTO archive_metadata VALUES('search_indexed','1')")
        # This migration removes age expiry; capacity is now the only automatic policy.
        if self.db.execute("SELECT 1 FROM archive_metadata WHERE key='capacity_retention'").fetchone() is None:
            with self.db:
                self.db.execute("UPDATE content SET expires_at=NULL WHERE expires_at IS NOT NULL")
                self.db.execute("UPDATE content SET data=json_set(data,'$.expires_at',?) WHERE kind IN ('posts','media')", (NO_EXPIRY,))
                self.db.execute("INSERT INTO archive_metadata VALUES('capacity_retention','1')")

    def index(self, row):
        marker = self.db.execute("SELECT received_before FROM source_read_marks WHERE source_id=?", (row["source_id"],)).fetchone()
        unread = self.db.execute("SELECT 1 FROM read_state WHERE id=?", (row["id"],)).fetchone() is None and (marker is None or row.get("received_at",row.get("published_at",0))>marker[0])
        route = self.db.execute("SELECT platform FROM source_routes WHERE id=?",(row["source_id"],)).fetchone()
        self.db.execute("""INSERT INTO post_index VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET source_id=excluded.source_id,published_at=excluded.published_at,received_at=excluded.received_at,state=excluded.state,saved=excluded.saved,unread=excluded.unread,title=excluded.title,has_media=excluded.has_media,has_links=excluded.has_links,platform=excluded.platform""", (
            row["id"], row["source_id"], row.get("published_at", 0), row.get("received_at", row.get("published_at", 0)), row.get("state", "active"), int(row.get("saved_at") is not None), int(unread), row.get("title"), int(bool(json.loads(row.get("media_ids", "[]")))), int(bool(row.get("url") or "http" in (row.get("body") or ""))),route[0] if route else ""
        ))
        identity = self.db.execute("SELECT rowid FROM post_index WHERE id=?", (row["id"],)).fetchone()[0]
        self.db.execute("DELETE FROM post_search WHERE rowid=?", (identity,))
        if row.get("state", "active") == "active":
            self.db.execute("INSERT INTO post_search(rowid,id,text) VALUES(?,?,?)", (identity, row["id"], ((row.get("title") or "")+'\n'+(row.get("body") or "")).lower()))

    def bundle(self, identifiers, budget=None):
        if not identifiers:
            return {"rows": [], "readStates": [], "postIds": []}
        if budget:
            found = {r[0]:r[1] for r in self.db.execute("SELECT item_key,data FROM content WHERE kind='posts' AND item_key IN (SELECT value FROM json_each(?))", (canonical(identifiers),))}
            chosen, size = [], 0
            for identifier in identifiers:
                amount = len(found.get(identifier, "").encode())
                if chosen and size+amount > budget: break
                chosen.append(identifier);size += amount
            identifiers = chosen
        values = canonical(identifiers)
        rows = [{"table": r["kind"], "row": json.loads(r["data"])} for r in self.db.execute("""SELECT kind,data FROM content WHERE (kind='posts' AND item_key IN (SELECT value FROM json_each(?))) OR (kind='media' AND json_extract(data,'$.post_id') IN (SELECT value FROM json_each(?)))""", (values, values))]
        reads = [{"entry_id": r[0], "read_at": r[1]} for r in self.db.execute("SELECT id,read_at FROM read_state WHERE id IN (SELECT value FROM json_each(?))", (values,))]
        known = {r["entry_id"] for r in reads}
        reads.extend({"entry_id":r[0],"read_at":r[1]} for r in self.db.execute("SELECT p.id,m.read_at FROM post_index p JOIN source_read_marks m ON m.source_id=p.source_id WHERE p.id IN (SELECT value FROM json_each(?)) AND p.received_at<=m.received_before",(values,)) if r[0] not in known)
        return {"rows": rows, "readStates": reads, "postIds": identifiers}

    def summaries(self):
        sources = []
        for row in self.db.execute("SELECT r.*,COALESCE(c.total,0) total,COALESCE(c.saved,0) saved,COALESCE(c.unread,0) unread FROM source_routes r LEFT JOIN source_counts c ON r.id=c.source_id"):
            last = self.db.execute("SELECT p.id,p.title,p.published_at,json_extract(c.data,'$.telegram') AS telegram FROM post_index p JOIN content c ON c.kind='posts' AND c.item_key=p.id WHERE p.source_id=? AND p.state='active' ORDER BY p.published_at DESC,p.id DESC LIMIT 1", (row["id"],)).fetchone()
            marker = self.db.execute("SELECT received_before,skipped FROM source_read_marks WHERE source_id=?",(row["id"],)).fetchone()
            unread = max(0,row["unread"]-(marker[1] if marker else 0));first = None
            if unread:
                index = "post_unread_received" if marker else "post_unread_time"
                first = self.db.execute("SELECT id,published_at FROM post_index INDEXED BY "+index+" WHERE source_id=? AND state='active' AND unread=1 AND received_at>? ORDER BY published_at,id LIMIT 1", (row["id"],marker[0] if marker else -1)).fetchone()
            sources.append({"sourceId": row["id"], "total": row["total"], "saved": row["saved"], "unread": unread, "last": dict(last) if last else None, "firstUnread": dict(first) if first else None})
        avatars = [{"sourceId": r[0], "sha256": r[1], "name": r[2], "mimeType": r[3]} for r in self.db.execute("SELECT item_key,json_extract(data,'$.sha256'),json_extract(data,'$.name'),json_extract(data,'$.mime_type') FROM content WHERE kind='source_avatars'")]
        return {"sources": sources, "avatars": avatars}

    def page(self, args):
        source_ids, limit = args.get("sourceIds", []), args.get("limit", 24)
        if not isinstance(source_ids, list) or len(source_ids) > 10000 or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("Invalid archive page")
        if not source_ids:return {"rows":[],"readStates":[],"postIds":[],"total":0,"nextCursor":None}
        where, params = ["p.state='active'", "p.source_id IN (SELECT value FROM json_each(?))"], [canonical(source_ids)]
        index = ""
        if not args.get("query"):
            platforms = [r[0] for r in self.db.execute("SELECT DISTINCT platform FROM source_routes WHERE id IN (SELECT value FROM json_each(?))",(canonical(source_ids),))]
            if len(source_ids)==1:index=" INDEXED BY post_source_time"
            elif len(platforms)==1:
                where.append("p.platform=?");params.append(platforms[0]);index=" INDEXED BY platform_time"
            else:index=" INDEXED BY post_time"
        if args.get("saved") is not None:
            where.append("p.saved=?"); params.append(int(args["saved"]))
        if args.get("media"):
            where.append("p.has_media=1")
        if args.get("links"):
            where.append("p.has_links=1")
        if args.get("since") is not None:
            where.append("p.published_at>=?");params.append(args["since"])
        if args.get("until") is not None:
            where.append("p.published_at<?");params.append(args["until"])
        if args.get("timeRanges"):
            ranges = args["timeRanges"]
            where.append("("+" OR ".join("(p.published_at>=? AND p.published_at<?)" for _ in ranges)+")")
            for window in ranges:params.extend([window["since"],window["until"]])
        def keyword(value):
            term = value.strip().lower()
            if len(term) >= 3 and '\0' not in term:
                body = "p.rowid IN (SELECT rowid FROM post_search WHERE post_search MATCH ?)"
                params.append('"'+term.replace('"','""')+'"')
            else:
                # Short Chinese words cannot use trigram MATCH. Read only rows
                # selected by the source/time indexes, not the entire text store.
                body = "EXISTS (SELECT 1 FROM post_search t WHERE t.rowid=p.rowid AND instr(t.text,?)>0)"
                params.append(term)
            params.append(term)
            return "("+body+" OR p.source_id IN (SELECT id FROM source_routes WHERE instr(lower(name),?)>0))"
        if args.get("query"):where.append(keyword(args["query"]))
        for word in args.get("keywordsAll", []):where.append(keyword(word))
        if args.get("keywordsAny"):where.append("("+" OR ".join(keyword(word) for word in args["keywordsAny"])+")")
        for word in args.get("excludeKeywords", []):where.append("NOT "+keyword(word))
        if args.get("order") == "discovery":
            seed, snapshot = args.get("seed"), args.get("snapshot")
            if not isinstance(seed, str) or not seed or not isinstance(snapshot, int):
                raise ValueError("Discovery requires a seed and snapshot")
            where.append("p.received_at<=?"); params.append(snapshot)
        elif isinstance(args.get("snapshot"), int):
            where.append("p.received_at<=?");params.append(args["snapshot"])
        selection = " FROM post_index p"+index+" WHERE " + " AND ".join(where)
        if args.get("order")=="discovery":total=0
        elif not any(args.get(key) for key in ("query","media","links","snapshot","timeRanges","keywordsAll","keywordsAny","excludeKeywords")) and not any(key in args for key in ("since","until")):
            column="saved" if args.get("saved") is True else "total-saved" if args.get("saved") is False else "total"
            total=self.db.execute("SELECT COALESCE(SUM("+column+"),0) FROM source_counts WHERE source_id IN (SELECT value FROM json_each(?))",(canonical(source_ids),)).fetchone()[0]
        else:total = self.db.execute("SELECT COUNT(*)" + selection, params).fetchone()[0]
        next_cursor = None
        if args.get("order") == "discovery":
            filters={key:args.get(key) for key in ("since","until","timeRanges","keywordsAll","keywordsAny","excludeKeywords")}
            identity = hashlib.sha256(canonical([source_ids, args.get("saved"), args.get("query"), filters, seed, snapshot, args.get("avoidFirst")]).encode()).hexdigest()
            if identity not in self.feeds:
                candidates = self.db.execute("SELECT p.id,p.published_at" + selection + " ORDER BY p.published_at DESC,p.id DESC LIMIT 768", params).fetchall()
                def score(row):
                    if row["id"] == args.get("avoidFirst"): return -1
                    random = int.from_bytes(hashlib.sha256((seed + '\0' + row["id"]).encode()).digest()[:4], "big") / 0xffffffff
                    return .65 / (1 + max(0, (snapshot-row["published_at"])/86400000)) + .35*random
                self.feeds[identity] = [r["id"] for r in sorted(candidates, key=lambda r: (score(r), r["id"]), reverse=True)]
                if len(self.feeds) > 32: self.feeds.pop(next(iter(self.feeds)))
            order = self.feeds[identity]; start = 0
            if args.get("cursor"):
                previous = uncursor(args["cursor"])
                if not isinstance(previous, dict) or previous.get("key") != identity or previous.get("after") not in order: raise ValueError("Feed cursor belongs to another refresh")
                start = order.index(previous["after"]) + 1
            identifiers = order[start:start+limit]
            if start+limit < len(order): next_cursor = cursor({"key": identity, "after": identifiers[-1]})
            total = len(order)
        else:
            if args.get("cursor"):
                previous = uncursor(args["cursor"])
                if not isinstance(previous, list) or len(previous) != 2: raise ValueError("Invalid news cursor")
                selection += " AND (p.published_at<? OR (p.published_at=? AND p.id<?))"; params.extend([previous[0], previous[0], previous[1]])
            ordering = "p.published_at DESC,(SELECT channel_id FROM source_routes r WHERE r.id=p.source_id),p.id" if args.get("messageOrder") else "p.published_at DESC,p.id DESC"
            rows = self.db.execute("SELECT p.id,p.published_at" + selection + " ORDER BY " + ordering + " LIMIT ? OFFSET ?", [*params, limit+1, args.get("offset", 0)]).fetchall()
            identifiers = [r["id"] for r in rows[:limit]]
            if len(rows) > limit: next_cursor = cursor([rows[limit-1]["published_at"], rows[limit-1]["id"]])
        bundle = self.bundle(identifiers, 4*1024*1024);identifiers = bundle["postIds"]
        if identifiers:
            if args.get("order") == "discovery":
                next_cursor = cursor({"key":identity,"after":identifiers[-1]}) if start+len(identifiers)<len(order) else None
            elif len(rows)>len(identifiers):
                last = rows[len(identifiers)-1];next_cursor = cursor([last["published_at"],last["id"]])
        return {**bundle, "nextCursor": next_cursor, "total": total}

    def execute(self, operation, args):
        if operation == "timeline-page":
            kind=args.get("kind","all");limit=args.get("limit",20);anchor=args.get("beforeEntry")
            if kind not in {"all","news","message"} or not isinstance(limit,int) or not 1<=limit<=100:raise ValueError("Invalid channel timeline page")
            news="SELECT id,published_at time,'news' kind FROM post_index WHERE state='active' AND source_id IN (SELECT value FROM json_each(?))"
            messages="SELECT item_key id,json_extract(data,'$.created_at') time,'message' kind FROM content WHERE kind='channel_messages' AND json_extract(data,'$.channel_id')=?"
            source=canonical(args["sourceIds"]);selection=news if kind=="news" else messages if kind=="message" else news+" UNION ALL "+messages
            params=[source] if kind=="news" else [args["id"]] if kind=="message" else [source,args["id"]]
            where=[]
            def earlier(stamp,identifier):
                where.append("(time<? OR (time=? AND id<?))");params.extend([stamp,stamp,identifier])
            if anchor is not None:
                row=self.db.execute("SELECT id,time FROM ("+news+" UNION ALL "+messages+") WHERE id=?",(source,args["id"],anchor)).fetchone()
                if row is None:raise ValueError("Timeline entry unavailable in this channel")
                earlier(row["time"],row["id"])
            if args.get("cursor"):
                c=uncursor(args["cursor"])
                if not isinstance(c,list) or len(c)!=6 or c[:4]!=[1,args["id"],kind,anchor]:raise ValueError("Timeline cursor belongs to another scope")
                earlier(c[4],c[5])
            rows=self.db.execute("SELECT id,time,kind FROM ("+selection+")"+(" WHERE "+" AND ".join(where) if where else "")+" ORDER BY time DESC,id DESC LIMIT ?",[*params,limit+1]).fetchall()
            chosen=[];size=0
            for r in rows[:limit]:
                raw=self.db.execute("SELECT data FROM content WHERE kind=? AND item_key=?",("posts" if r["kind"]=="news" else "channel_messages",r["id"])).fetchone()
                amount=len(raw[0].encode()) if raw else 0
                if chosen and size+amount>4*1024*1024:break
                chosen.append(dict(r));size+=amount
            bundle=self.bundle([r["id"] for r in chosen if r["kind"]=="news"])
            for r in chosen:
                if r["kind"]=="message":bundle["rows"].extend(self.message_rows(r["id"]))
            last=chosen[-1] if chosen else None
            return {**bundle,"entries":list(reversed(chosen)),"nextCursor":cursor([1,args["id"],kind,anchor,last["time"],last["id"]]) if len(rows)>len(chosen) and last else None,"order":"chronological"}
        if operation == "configure":
            with self.db:
                for source in args.get("sources", []):
                    self.db.execute("INSERT INTO source_routes VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET platform=excluded.platform,channel_id=excluded.channel_id,name=excluded.name", (source["id"], source["plugin"], source["channel_id"], source["name"]))
                self.db.execute("UPDATE post_index SET platform=COALESCE((SELECT platform FROM source_routes WHERE id=post_index.source_id),'') WHERE platform=''")
            self.store.capacity.initialize()
            return {"retentionDays": None, "platformCapacityBytes": {p: PLATFORM_BYTES for p in ("telegram", "x", "youtube")}}
        if operation == "summaries": return self.summaries()
        if operation == "posts-page": return self.page(args)
        if operation == "post-get": return self.bundle([args["id"]])
        if operation == "read-states":
            entries=[];allowed=set(args["sourceIds"])
            for identifier in args["ids"]:
                post=self.db.execute("SELECT source_id,received_at FROM post_index WHERE id=? AND state='active'",(identifier,)).fetchone()
                if post is None:continue
                if post[0] not in allowed:raise ValueError("Entry belongs to another channel")
                known=self.db.execute("SELECT read_at FROM read_state WHERE id=?",(identifier,)).fetchone()
                marker=self.db.execute("SELECT received_before,read_at FROM source_read_marks WHERE source_id=?",(post[0],)).fetchone()
                stamp=known[0] if known else marker[1] if marker and post[1]<=marker[0] else None
                state=("unknown" if stamp is None else "read") if known else "read" if stamp is not None else "unread"
                entries.append({"id":identifier,"state":state,**({"readAt":stamp} if stamp is not None else {})})
            return {"entries":entries}
        if operation in {"reads-import", "read-mark"}:
            values = args.get("entries", [])
            if args.get("all"):
                marked = 0
                with self.db:
                    for source in args["sourceIds"]:
                        count = self.db.execute("SELECT c.unread,COALESCE(m.skipped,0),COALESCE(m.received_before,0) FROM source_counts c LEFT JOIN source_read_marks m ON m.source_id=c.source_id WHERE c.source_id=?",(source,)).fetchone()
                        if count:
                            cutoff=max(count[2],args["readAt"])
                            later=self.db.execute("SELECT count(*) FROM post_index WHERE source_id=? AND state='active' AND unread=1 AND received_at>?",(source,cutoff)).fetchone()[0]
                            skipped=count[0]-later
                            marked += max(0,skipped-count[1]);self.db.execute("INSERT INTO source_read_marks VALUES(?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET received_before=excluded.received_before,read_at=excluded.read_at,skipped=excluded.skipped",(source,cutoff,cutoff,skipped))
                return {"marked":marked}
            with self.db:
                for row in values:
                    self.db.execute("INSERT INTO read_state VALUES(?,?) ON CONFLICT(id) DO UPDATE SET read_at=COALESCE(excluded.read_at,read_at)", (row["entry_id"], row.get("read_at")))
                    self.db.execute("UPDATE post_index SET unread=0 WHERE id=? AND unread<>0", (row["entry_id"],))
            return {"marked": len(values)}
        if operation == "avatar-get":
            row = self.db.execute("SELECT data FROM content WHERE kind='source_avatars' AND item_key=?", (args["sourceId"],)).fetchone()
            if row is None: raise FileNotFoundError("Source avatar unavailable")
            return {"rows": [{"table": "source_avatars", "row": json.loads(row[0])}]}
        if operation == "history-page":
            if args.get("around"):
                rows=self.db.execute("SELECT item_key FROM content WHERE kind='channel_messages' AND item_key=? AND json_extract(data,'$.channel_id')=?",(args["around"],args["id"])).fetchall()
            else:rows = self.db.execute("SELECT item_key FROM content WHERE kind='channel_messages' AND json_extract(data,'$.channel_id')=? AND json_extract(data,'$.sequence')<? ORDER BY json_extract(data,'$.sequence') DESC LIMIT ?", (args["id"], args.get("before", 9007199254740991), args.get("limit", 100)+1)).fetchall()
            return {"rows": [value for row in rows for value in self.message_rows(row[0])]}
        raise ValueError("Unsupported archive query")

    def message_rows(self, identifier):
        rows=self.db.execute("SELECT kind,data FROM content WHERE (kind='channel_messages' AND item_key=?) OR (kind IN ('channel_message_attachments','channel_message_notices','channel_message_triggers') AND json_extract(data,'$.message_id')=?)",(identifier,identifier))
        return [{"table":r["kind"],"row":json.loads(r["data"])} for r in rows]
