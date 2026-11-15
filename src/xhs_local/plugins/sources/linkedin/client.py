"""Public guest-page structured posts; no login automation or private member data."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit

from xhs_local.configuration.knowledge_sources import linkedin_homepage as homepage
from xhs_local.core.errors import AuthenticationRequired, ValidationFailure
from xhs_local.plugins.sources.public_content import PublicClient, PublicPost


class GuestPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scripts, self.script, self.article, self.media, self.avatars = [], None, None, {}, {}
        self.canonical = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href")
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.script = []
        if tag == "article":
            self.article = attrs.get("data-activity-urn")
        if tag == "img" and self.article:
            url = attrs.get("data-delayed-url") or attrs.get("src") or ""
            if urlsplit(url).hostname not in {
                "media.licdn.com",
                "media-exp1.licdn.com",
                "media-exp2.licdn.com",
            }:
                return
            if "company-logo" in url or "profile-displayphoto" in url:
                self.avatars.setdefault(self.article, url)
            elif url and "ghost" not in url:
                self.media.setdefault(self.article, []).append(url)

    def handle_data(self, text):
        if self.script is not None:
            self.script.append(text)

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            self.scripts.append("".join(self.script))
            self.script = None
        if tag == "article":
            self.article = None


def informative(text: str) -> bool:
    """Density/originality filter, never a claim that the text is factually proven."""
    compact = " ".join(text.split())
    if len(compact) < 160:
        return False
    promotion = re.search(
        r"we(?:’|'| a)re hiring|join our team|save your spot|register now|apply now|giveaway"
        r"|招聘|立即报名|抽奖",
        compact,
        re.I,
    )
    return not promotion


def parse_page(body: bytes, expected: str) -> list[PublicPost]:
    parser = GuestPage()
    text = body.decode("utf-8", "replace")
    parser.feed(text)
    if parser.canonical:
        expected = homepage(parser.canonical)
    nodes = []
    for script in parser.scripts:
        try:
            value = json.loads(script)
        except ValueError:
            continue
        nodes.extend(
            value.get("@graph", [value])
            if isinstance(value, dict)
            else value
            if isinstance(value, list)
            else []
        )
    posts = []
    for node in nodes:
        if not isinstance(node, dict) or node.get("@type") != "SocialMediaPosting":
            continue
        author = node.get("author", {})
        try:
            if homepage(author.get("url", "")) != expected:
                # A repost from another author is not an original account update.
                continue
        except (ValueError, ValidationFailure):
            continue
        url = node.get("url") or node.get("mainEntityOfPage")
        if not isinstance(url, str) or urlsplit(url).hostname not in {
            "www.linkedin.com",
            "linkedin.com",
        }:
            continue
        identifier = re.search(r"(?:activity-|activity:)(\d+)", url)
        content = node.get("text")
        if not identifier or not isinstance(content, str) or not informative(content):
            continue
        try:
            published = datetime.fromisoformat(str(node["datePublished"]).replace("Z", "+00:00"))
            if published.tzinfo is None:
                continue
        except (KeyError, ValueError):
            continue
        urn = "urn:li:activity:" + identifier[1]
        title = next(
            (line.strip() for line in content.splitlines() if line.strip()),
            author.get("name", "LinkedIn"),
        )[:180]
        posts.append(
            PublicPost(
                id=identifier[1],
                time=published.astimezone(UTC),
                text=content.strip(),
                title=title,
                url=url.split("?", 1)[0],
                author=str(author.get("name") or expected),
                author_url=expected,
                images=tuple(dict.fromkeys(parser.media.get(urn, []))),
                avatar=parser.avatars.get(urn),
                metadata={
                    "collection_scope": "public_original_posts",
                    "time_basis": "platform_datePublished",
                },
            )
        )
    if not nodes and (
        "authwall" in text.lower()
        or "checkpoint/challenge" in text.lower()
        or re.search(
            r"<title>[^<]*(?:LinkedIn Login|Sign In[^<]*LinkedIn|Security Verification)", text, re.I
        )
    ):
        raise AuthenticationRequired("LinkedIn public posts require authorized access")
    return posts


class LinkedInClient(PublicClient):
    def __init__(self, **kwargs):
        super().__init__(("linkedin.com", "licdn.com"), **kwargs)

    async def posts(self, locator: str, deadline=None) -> list[PublicPost]:
        expected = homepage(locator)
        response = await self.get(expected, deadline)
        if response.url and any(
            part in urlsplit(response.url).path for part in ["/authwall", "/login", "/checkpoint"]
        ):
            raise AuthenticationRequired("LinkedIn redirected to sign-in; collection was stopped")
        return parse_page(response.body, expected)
