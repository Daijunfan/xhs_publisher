"""Public Reddit Atom subscriptions; no private JSON, login replay or challenge bypass."""

from __future__ import annotations

import asyncio
import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit

from xhs_local.configuration.knowledge_sources import reddit_homepage
from xhs_local.core.errors import ErrorClass, TransientError, ValidationFailure
from xhs_local.plugins.sources.public_content import PublicClient, PublicPost

ATOM = "{http://www.w3.org/2005/Atom}"
MEDIA = "{http://search.yahoo.com/mrss/}"


class FeedBody(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.images = [], [], []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style"}:
            self.skip += 1
        if self.skip:
            return
        if tag in {"p", "div", "blockquote", "li", "h1", "h2", "h3", "pre"}:
            self.parts.append("\n\n" if tag != "li" else "\n- ")
        if tag == "br":
            self.parts.append("\n")
        if tag in {"strong", "b"}:
            self.parts.append("**")
        if tag == "a":
            href = attrs.get("href", "")
            self.links.append(href if urlsplit(href).scheme in {"http", "https"} else "")
        if tag == "img":
            self.images.append(attrs.get("src", ""))

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in {"strong", "b"}:
            self.parts.append("**")
        if tag in {"p", "div", "blockquote", "li", "h1", "h2", "h3", "pre"}:
            self.parts.append("\n\n")
        if tag == "a" and self.links:
            href = self.links.pop()
            if href:
                self.parts.append(" (" + href + ")")

    def text(self):
        return re.sub(r"\n[ \t]*\n(?:\s*\n)+", "\n\n", "".join(self.parts)).strip()


def parse_feed(body: bytes, locator: str) -> list[PublicPost]:
    expected = reddit_homepage(locator)
    try:
        feed = ET.fromstring(body)
    except ET.ParseError as error:
        raise ValidationFailure("Reddit did not return an Atom feed") from error
    if feed.tag != ATOM + "feed":
        raise ValidationFailure("Reddit returned a login/error page instead of a feed")
    posts = []
    for entry in feed.findall(ATOM + "entry"):
        identifier = entry.findtext(ATOM + "id", "")
        title = entry.findtext(ATOM + "title", "").strip()
        link = entry.find(ATOM + "link")
        url = link.get("href", "") if link is not None else ""
        if not re.fullmatch(r"t3_[a-z0-9]+", identifier) or not title:
            continue
        if urlsplit(url).hostname not in {"www.reddit.com", "reddit.com"}:
            continue
        category = entry.find(ATOM + "category")
        community = category.get("term", "") if category is not None else ""
        author = entry.findtext(ATOM + "author/" + ATOM + "name", "")
        author_url = entry.findtext(ATOM + "author/" + ATOM + "uri")
        kind, name = urlsplit(expected).path.strip("/").split("/")
        if kind == "r" and not urlsplit(url).path.lower().startswith("/r/" + name + "/"):
            continue
        if kind == "user" and author.removeprefix("/u/").removeprefix("u/").lower() != name:
            continue
        try:
            published = datetime.fromisoformat(
                entry.findtext(ATOM + "published", "").replace("Z", "+00:00")
            )
            if published.tzinfo is None:
                raise ValueError("Missing timezone")
        except ValueError as error:
            raise ValidationFailure("Reddit post is missing its publication timestamp") from error
        parser = FeedBody()
        content = entry.findtext(ATOM + "content", "")
        # The feed's submission footer is attribution, not part of the post body.
        parser.feed(
            content.split("<!-- SC_ON -->", 1)[0] if "<!-- SC_OFF -->" in content else content
        )
        text = parser.text()
        if text.strip().lower() in {"[removed]", "[deleted]"}:
            continue
        images = list(parser.images)
        thumbnail = entry.find(MEDIA + "thumbnail")
        if not images and thumbnail is not None:
            images.append(thumbnail.get("url", ""))
        images = [
            u
            for u in images
            if urlsplit(u).scheme == "https"
            and urlsplit(u).hostname
            in {
                "i.redd.it",
                "preview.redd.it",
                "external-preview.redd.it",
                "b.thumbs.redditmedia.com",
                "a.thumbs.redditmedia.com",
            }
        ]
        posts.append(
            PublicPost(
                id=identifier,
                time=published.astimezone(UTC),
                text=text or title,
                title=title,
                url=url,
                author=author or "Reddit",
                author_url=author_url,
                images=tuple(dict.fromkeys(images)),
                metadata={
                    "collection_scope": "public_atom_feed",
                    "subreddit": community,
                    "original_post_id": identifier,
                    "feed_updated_at": entry.findtext(ATOM + "updated"),
                    "comments_url": url,
                },
            )
        )
    return posts


class RedditClient(PublicClient):
    def __init__(self, **kwargs):
        super().__init__(("reddit.com", "redd.it", "redditmedia.com"), **kwargs)
        self.feed_lock = asyncio.Lock()
        self.next_request_at = 0.0

    async def posts(self, locator, deadline=None, limit=25):
        homepage = reddit_homepage(locator)
        suffix = "new/.rss" if "/r/" in homepage else "submitted/.rss"
        async with self.feed_lock:
            delay = self.next_request_at - time.monotonic()
            if delay > 0:
                if deadline is not None and time.monotonic() + delay >= deadline:
                    error = TransientError("Reddit RSS is cooling down after rate limiting")
                    error.error_class = ErrorClass.RATE_LIMITED
                    raise error
                await asyncio.sleep(delay)
            self.next_request_at = time.monotonic() + 15
            try:
                response = await self.get(homepage + suffix + "?limit=" + str(limit), deadline)
            except TransientError as error:
                if error.error_class == ErrorClass.RATE_LIMITED:
                    self.next_request_at = time.monotonic() + 900
                raise
        return parse_feed(response.body, homepage)
