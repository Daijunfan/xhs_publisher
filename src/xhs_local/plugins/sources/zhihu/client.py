"""Zhihu's public editorial originals and substantive public discussion."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

from xhs_local.configuration.knowledge_sources import zhihu_locator_kind as locator_kind
from xhs_local.core.errors import AuthenticationRequired, ValidationFailure
from xhs_local.plugins.sources.public_content import PublicClient, PublicPost

API = "https://news-at.zhihu.com/api/4"


class DailyBody(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth, self.answer_depth, self.content_depth, self.field = 0, None, None, None
        self.current, self.answers = None, []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        void = tag in {"img", "br", "hr", "meta", "link", "input", "source", "wbr"}
        if not void:
            self.depth += 1
        classes = attrs.get("class", "").split()
        if tag == "div" and "answer" in classes:
            self.current = {
                "author": "",
                "bio": "",
                "avatar": None,
                "origin": None,
                "parts": [],
                "images": [],
            }
            self.answer_depth = self.depth
        if self.current is None:
            return
        if tag == "div" and "content" in classes:
            self.content_depth = self.depth
        if tag == "span" and ("author" in classes or "bio" in classes):
            self.field = ("author" if "author" in classes else "bio", self.depth)
        if tag == "img":
            url = attrs.get("src", "")
            if "avatar" in classes:
                self.current["avatar"] = url
            elif self.content_depth:
                self.current["images"].append(url)
        if tag == "a":
            url = attrs.get("href", "")
            if "originUrl" in classes:
                self.current["origin"] = url
            if self.content_depth:
                self.links.append((self.depth, url))
        if tag == "br" and self.content_depth:
            self.current["parts"].append("\n")

    def handle_data(self, text):
        if self.current is None:
            return
        if self.content_depth:
            self.current["parts"].append(text)
        elif self.field:
            self.current[self.field[0]] += text

    def handle_endtag(self, tag):
        if self.current:
            if self.content_depth and tag in {
                "p",
                "li",
                "blockquote",
                "figcaption",
                "h2",
                "h3",
                "h4",
            }:
                self.current["parts"].append("\n\n")
            if tag == "a" and self.links and self.links[-1][0] == self.depth:
                _, url = self.links.pop()
                if url.startswith(("https://", "http://")):
                    self.current["parts"].append(" (" + url + ")")
            if self.field and self.field[1] == self.depth:
                self.field = None
            if self.content_depth == self.depth and tag == "div":
                self.content_depth = None
            if self.answer_depth == self.depth and tag == "div":
                self.answers.append(self.current)
                self.current, self.answer_depth, self.content_depth, self.field = (
                    None,
                    None,
                    None,
                    None,
                )
        self.depth = max(0, self.depth - 1)


def parse_story(data: dict, selected_date: str) -> list[PublicPost]:
    if not isinstance(data.get("body"), str) or not data.get("id") or not data.get("title"):
        raise ValidationFailure("Zhihu editorial item is missing original content")
    day = (
        datetime.strptime(selected_date, "%Y%m%d")
        .replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        .astimezone(UTC)
    )
    parser = DailyBody()
    parser.feed(data["body"])
    posts = []
    editorial_url = "https://daily.zhihu.com/story/" + str(data["id"])
    for answer in parser.answers:
        author = answer["author"].strip().rstrip("，,")
        content = re.sub(r"[ \t]+", " ", "".join(answer["parts"]))
        content = re.sub(r"\n\s*\n(?:\s*\n)+", "\n\n", content).strip()
        if not author or len(content) < 80:
            continue
        original = answer["origin"]
        match = re.search(r"/answer/(\d+)", original or "")
        identity = (
            "answer:" + match[1]
            if match
            else "editorial:"
            + str(data["id"])
            + ":"
            + hashlib.sha256(author.encode()).hexdigest()[:12]
        )
        footer = (
            "\n\n---\n知乎日报精选："
            + editorial_url
            + "\n选刊日期："
            + selected_date[:4]
            + "-"
            + selected_date[4:6]
            + "-"
            + selected_date[6:]
        )
        if original:
            footer += "\n知乎原文：" + original
        posts.append(
            PublicPost(
                id=identity,
                time=day,
                text=content + footer,
                title=data["title"],
                url=original or editorial_url,
                author=author,
                images=tuple(dict.fromkeys(answer["images"])),
                avatar=answer["avatar"],
                metadata={
                    "content_kind": "answer" if match else "editorial",
                    "collection_scope": "public_editorial_selection",
                    "time_basis": "editorial_selection_date",
                    "time_precision": "day",
                    "selected_date": selected_date,
                    "editorial_url": editorial_url,
                    "original_url": original,
                },
            )
        )
    return posts


def valuable_comment(text: str, likes: int = 0) -> bool:
    compact = " ".join(text.split())
    if len(compact) < 80 or re.search(r"加我微信|私信咨询|扫码|推广合作|免费领取", compact):
        return False
    return (
        likes >= 2
        or len(compact) >= 160
        or bool(
            re.search(r"https?://|数据|研究|证据|例如|因为|原因|原理|实际上|补充|参考", compact)
        )
    )


class ZhihuClient(PublicClient):
    def __init__(self, **kwargs):
        super().__init__(("zhihu.com", "zhimg.com"), **kwargs)

    async def posts(
        self, locator: str, deadline=None, *, days=3, include_comments=True, comment_min_chars=80
    ):
        if locator_kind(locator) != "editorial":
            raise AuthenticationRequired(
                "Zhihu author collection requires authorized platform access; "
                "the current public route covers editorial selections "
                "and their public comments only"
            )
        latest = await self.json(API + "/news/latest", deadline)
        current = latest.get("date")
        if not isinstance(current, str) or not re.fullmatch(r"\d{8}", current):
            raise ValidationFailure("Zhihu public feed has no publication date")
        indexes = [latest]
        date = datetime.strptime(current, "%Y%m%d")
        for offset in range(1, min(int(days), 8)):
            before = (date - timedelta(days=offset - 1)).strftime("%Y%m%d")
            indexes.append(await self.json(API + "/news/before/" + before, deadline))
        posts = []
        for index in reversed(indexes):
            for story in index.get("stories", []):
                data = await self.json(API + "/news/" + str(story["id"]), deadline)
                originals = parse_story(data, index["date"])
                posts.extend(originals)
                if not include_comments:
                    continue
                for kind in ["long-comments", "short-comments"]:
                    comments = await self.json(
                        API + "/story/" + str(story["id"]) + "/" + kind, deadline
                    )
                    for comment in comments.get("comments", []):
                        content = comment.get("content", "")
                        if (
                            not isinstance(content, str)
                            or len(content) < comment_min_chars
                            or not valuable_comment(content, int(comment.get("likes") or 0))
                        ):
                            continue
                        stamp = comment.get("time")
                        if not isinstance(stamp, (int, float)) or not comment.get("id"):
                            continue
                        url = "https://daily.zhihu.com/story/" + str(story["id"])
                        text = "讨论原题：" + data["title"] + "\n\n" + content
                        reply = comment.get("reply_to")
                        if isinstance(reply, dict) and reply.get("content"):
                            text += (
                                "\n\n回复 "
                                + str(reply.get("author") or "原评论")
                                + "：\n> "
                                + str(reply["content"])
                            )
                        text += "\n\n原讨论：" + url
                        posts.append(
                            PublicPost(
                                id="comment:" + str(comment["id"]),
                                time=datetime.fromtimestamp(stamp, UTC),
                                text=text,
                                title="[评论] " + data["title"],
                                url=url,
                                author=str(comment.get("author") or "知乎日报用户"),
                                avatar=comment.get("avatar"),
                                metadata={
                                    "content_kind": "comment",
                                    "parent_story_id": story["id"],
                                    "comment_id": comment["id"],
                                    "likes": comment.get("likes", 0),
                                    "collection_scope": "public_editorial_discussion",
                                    "time_basis": "platform_comment_time",
                                },
                            )
                        )
        return list({post.id: post for post in posts}.values())
