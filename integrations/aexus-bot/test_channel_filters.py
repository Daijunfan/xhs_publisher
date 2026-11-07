"""Offline acceptance for channel news filters over the real archive database.

Every fixture uses a temporary store and the real ``posts-page``/FTS5 query path.
No network, model calls or production state are involved.
"""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from channel_content import ChannelContentStore

PLUS_EIGHT = timezone(timedelta(hours=8))


def local_ms(day, hour, minute, second=0, microsecond=0):
    """Epoch milliseconds for a November 2026 wall time in +08:00."""
    return round(datetime(2026, 11, day, hour, minute, second, microsecond, tzinfo=PLUS_EIGHT).timestamp() * 1000)


class ChannelFilterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aexus-channel-filters-")
        self.store = ChannelContentStore(Path(self.temp.name))
        self.store.execute("configure", {"sources": [
            {"id": "x", "plugin": "x", "channel_id": "x-channel", "name": "x"},
            {"id": "youtube", "plugin": "youtube", "channel_id": "youtube-channel", "name": "youtube"},
            {"id": "telegram", "plugin": "telegram", "channel_id": "telegram-channel", "name": "telegram"},
        ]})

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def post(self, identifier, source, published, body, received=None):
        row = {
            "id": identifier, "source_id": source, "state": "active",
            "published_at": published, "received_at": published if received is None else received,
            "saved_at": None, "title": "", "body": body,
            "media_ids": "[]", "remote_files": "[]",
        }
        self.store.execute("write", {"changes": [{"table": "posts", "key": identifier, "row": row}]})

    def page(self, **args):
        args.setdefault("limit", 100)
        return self.store.execute("posts-page", args)

    def keyword_posts(self):
        for identifier, published, body in (
            ("both", 5000, "OpenAI 与 金融 行业观察"),
            ("upper", 4900, "OPENAI 与 金融 市场"),
            ("lower", 4800, "openai 与 金融 案例"),
            ("finance-only", 4700, "金融 行业观察"),
            ("ai-only", 4600, "OpenAI 行业观察"),
            ("ad-openai", 4550, "OpenAI 金融 广告 推广"),
            ("ad", 4500, "金融 广告 推广"),
            ("none", 4400, "天气很好"),
        ):
            self.post(identifier, "x", published, body)

    def test_source_ids_are_or_filtered(self):
        self.post("x-old", "x", 1000, "x 旧闻")
        self.post("x-new", "x", 2000, "x 新闻")
        self.post("yt", "youtube", 1500, "youtube 新闻")
        self.post("tg", "telegram", 1200, "telegram 新闻")
        result = self.page(sourceIds=["x", "youtube"])
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["postIds"], ["x-new", "yt", "x-old"])
        self.assertEqual(self.page(sourceIds=["telegram"])["postIds"], ["tg"])
        self.assertEqual(self.page(sourceIds=["x", "telegram"], until=1300)["postIds"], ["tg", "x-old"])

    def test_since_is_inclusive_and_until_is_exclusive(self):
        for identifier, published in (("before", 999), ("start", 1000), ("inside", 1999), ("end", 2000)):
            self.post(identifier, "x", published, "时间边界")
        result = self.page(sourceIds=["x"], since=1000, until=2000)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["postIds"], ["inside", "start"])

    def test_time_ranges_are_unioned(self):
        for identifier, published in (("early", 99), ("first", 150), ("gap", 350), ("second", 550), ("edge", 600)):
            self.post(identifier, "x", published, "时间段")
        result = self.page(sourceIds=["x"], timeRanges=[{"since": 100, "until": 200}, {"since": 500, "until": 600}])
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["postIds"], ["second", "first"])

    def test_keywords_all_requires_every_keyword(self):
        self.keyword_posts()
        result = self.page(sourceIds=["x"], keywordsAll=["OpenAI", "金融"])
        self.assertEqual(result["total"], 4)
        self.assertEqual(result["postIds"], ["both", "upper", "lower", "ad-openai"])

    def test_keywords_any_is_an_or(self):
        self.keyword_posts()
        result = self.page(sourceIds=["x"], keywordsAny=["OpenAI", "金融"])
        self.assertEqual(result["total"], 7)
        self.assertEqual(result["postIds"], ["both", "upper", "lower", "finance-only", "ai-only", "ad-openai", "ad"])

    def test_exclude_and_combined_keyword_filters(self):
        self.keyword_posts()
        excluded = self.page(sourceIds=["x"], excludeKeywords=["广告"])
        self.assertEqual(excluded["total"], 6)
        self.assertNotIn("ad-openai", excluded["postIds"])
        self.assertNotIn("ad", excluded["postIds"])
        combined = self.page(sourceIds=["x"], keywordsAll=["金融"], keywordsAny=["OpenAI", "案例"], excludeKeywords=["广告"])
        self.assertEqual(combined["total"], 3)
        self.assertEqual(combined["postIds"], ["both", "upper", "lower"])

    def test_english_keywords_ignore_case(self):
        self.keyword_posts()
        upper = self.page(sourceIds=["x"], keywordsAll=["OPENAI"])
        lower = self.page(sourceIds=["x"], keywordsAll=["openai"])
        self.assertEqual(upper["total"], 5)
        self.assertEqual(upper["postIds"], ["both", "upper", "lower", "ai-only", "ad-openai"])
        self.assertEqual(upper["postIds"], lower["postIds"])
        self.assertEqual(upper["total"], lower["total"])

    def test_two_character_chinese_keyword_matches_substring(self):
        self.post("embedded", "x", 100, "互联网金融趋势")
        self.post("split", "x", 99, "金 融 分开")
        result = self.page(sourceIds=["x"], keywordsAll=["金融"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["postIds"], ["embedded"])

    def test_query_text_is_literal_not_fts_syntax(self):
        self.post("quoted", "x", 100, '官方称 "OpenAI" 是研究机构')
        self.post("plain", "x", 99, "官方称 OpenAI 是研究机构")
        self.post("paren", "x", 98, "机构(OpenAI)发布")
        self.post("bare", "x", 97, "机构OpenAI发布")
        self.post("open-quote", "x", 96, '标题 "Aexus 研究')
        self.post("open-plain", "x", 95, "标题 Aexus 研究")
        quoted = self.page(sourceIds=["x"], query='"OpenAI"')
        self.assertEqual(quoted["total"], 1)
        self.assertEqual(quoted["postIds"], ["quoted"])
        paren = self.page(sourceIds=["x"], query="(OpenAI)")
        self.assertEqual(paren["total"], 1)
        self.assertEqual(paren["postIds"], ["paren"])
        unbalanced = self.page(sourceIds=["x"], query='"Aexus')
        self.assertEqual(unbalanced["total"], 1)
        self.assertEqual(unbalanced["postIds"], ["open-quote"])

    def test_cursor_pagination_has_no_duplicates_or_gaps(self):
        fixtures = []
        for index in range(30):
            identifier = "n%02d" % index
            published = 1000 + (index % 7) * 100
            self.post(identifier, "x" if index % 2 else "youtube", published, "分页")
            fixtures.append((identifier, published))
        expected = [identifier for identifier, _ in sorted(fixtures, key=lambda item: (item[1], item[0]), reverse=True)]
        seen, cursor, pages = [], None, 0
        while True:
            args = {"sourceIds": ["x", "youtube"], "limit": 7}
            if cursor is not None:
                args["cursor"] = cursor
            result = self.store.execute("posts-page", args)
            self.assertEqual(result["total"], 30)
            self.assertLessEqual(len(result["postIds"]), 7)
            seen.extend(result["postIds"])
            cursor = result["nextCursor"]
            pages += 1
            self.assertLess(pages, 50)
            if cursor is None:
                break
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(seen, expected)

    def test_discovery_cursor_is_scoped_to_filters_and_refresh(self):
        for index in range(20):
            self.post("d%02d" % index, "x" if index % 2 else "youtube", 100 + index, "OpenAI 新闻")
        base = {"sourceIds": ["x", "youtube"], "order": "discovery", "seed": "feed", "snapshot": 130, "limit": 5}
        first = self.store.execute("posts-page", base)
        self.assertEqual(first["total"], 20)
        self.assertEqual(len(first["postIds"]), 5)
        second = self.store.execute("posts-page", {**base, "cursor": first["nextCursor"]})
        self.assertEqual(second["total"], 20)
        self.assertEqual(len(second["postIds"]), 5)
        self.assertFalse(set(first["postIds"]) & set(second["postIds"]))
        for changed in (
            {"sourceIds": ["x"]},
            {"query": "OpenAI"},
            {"saved": True},
            {"since": 100},
            {"until": 120},
            {"timeRanges": [{"since": 100, "until": 200}]},
            {"keywordsAll": ["金融"]},
            {"keywordsAny": ["OpenAI"]},
            {"excludeKeywords": ["广告"]},
            {"seed": "other-feed"},
            {"snapshot": 140},
        ):
            with self.assertRaises(ValueError, msg=str(changed)):
                self.store.execute("posts-page", {**base, **changed, "cursor": first["nextCursor"]})
        news_cursor = self.store.execute("posts-page", {"sourceIds": ["x"], "limit": 2})["nextCursor"]
        with self.assertRaises(ValueError):
            self.store.execute("posts-page", {**base, "cursor": news_cursor})
        with self.assertRaises(ValueError):
            self.store.execute("posts-page", {"sourceIds": ["x"], "limit": 2, "cursor": first["nextCursor"]})

    def test_reference_2026_11_05_afternoon_windows(self):
        day_before_start, day_before_end = local_ms(3, 14, 30), local_ms(3, 15, 30)
        yesterday_start, yesterday_end = local_ms(4, 14, 30), local_ms(4, 15, 30)
        self.post("y-start", "x", yesterday_start, "金融 市场更新")
        self.post("y-mid", "x", local_ms(4, 15, 0), "金融 市场更新 第二篇")
        self.post("y-end", "x", yesterday_end, "金融 市场更新 第三篇")
        self.post("y-before", "x", local_ms(4, 14, 29, 59, 999000), "金融 市场更新 第四篇")
        self.post("d-mid", "x", local_ms(3, 15, 0), "金融 前天更新")
        self.post("older", "x", local_ms(2, 15, 0), "金融 更早更新")
        self.post("other-author", "youtube", local_ms(4, 15, 0), "金融 另一来源")
        self.post("no-keyword", "x", local_ms(4, 15, 0), "天气预报")
        self.post("excluded", "x", local_ms(4, 15, 0), "金融 广告 推广")
        result = self.page(
            sourceIds=["x"],
            timeRanges=[
                {"since": yesterday_start, "until": yesterday_end},
                {"since": day_before_start, "until": day_before_end},
            ],
            keywordsAll=["金融"],
            excludeKeywords=["广告"],
        )
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["postIds"], ["y-mid", "y-start", "d-mid"])
        for identifier in ("y-end", "y-before", "older", "other-author", "no-keyword", "excluded"):
            self.assertNotIn(identifier, result["postIds"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
