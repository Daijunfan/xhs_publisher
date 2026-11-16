import asyncio
import time
from datetime import UTC, datetime
from html import escape
from pathlib import Path

import pytest

from xhs_local.configuration.knowledge_sources import reddit_homepage
from xhs_local.configuration.subscriptions import collector_locator
from xhs_local.core.errors import (
    AuthenticationRequired,
    ErrorClass,
    TransientError,
    ValidationFailure,
)
from xhs_local.plugins.contracts import CollectRequest, PluginTarget, SourcePluginContext
from xhs_local.plugins.registry import SourcePluginRegistry
from xhs_local.plugins.sources.public_content import PublicResponse, collect_public
from xhs_local.plugins.sources.reddit.client import RedditClient, parse_feed

NOW = datetime(2026, 11, 16, 12, tzinfo=UTC)
URL = "https://www.reddit.com/r/fixture/"


def feed(
    content='<p>Original <strong>research</strong> with <a href="https://example.org/paper">evidence</a>.</p>',
    stamp="2026-11-16T10:00:00Z",
    community="fixture",
):
    return f'''<feed xmlns="http://www.w3.org/2005/Atom">
<title>Fixture</title><entry><id>t3_abc123</id><title>Research update</title>
<published>{stamp}</published><updated>2026-11-16T11:00:00Z</updated>
<author><name>/u/Researcher</name>
<uri>https://www.reddit.com/user/Researcher/</uri></author>
<category term="{community}"/>
<link href="https://www.reddit.com/r/{community}/comments/abc123/research/"/>
<content type="html">{escape(content)}</content></entry></feed>'''.encode()


def test_url_identity_and_scope():
    for value in ["r/Fixture", "/r/fixture", URL, "https://old.reddit.com/r/FIXTURE/new?sort=new"]:
        assert reddit_homepage(value) == URL
        assert collector_locator("reddit", value) == URL
    assert reddit_homepage("u/Researcher") == "https://www.reddit.com/user/researcher/"
    for value in [
        "https://reddit.com.evil.test/r/fixture/",
        "https://a:b@reddit.com/r/fixture/",
        "https://reddit.com/r/a+b/",
        "https://reddit.com/r/all/",
        URL + "comments/abc123/",
        "file:///r/fixture",
        "https://reddit.com:999/r/fixture",
    ]:
        with pytest.raises(ValueError):
            reddit_homepage(value)


def test_atom_keeps_original_author_publication_links_and_scope():
    post = parse_feed(feed(), URL)[0]
    assert post.id == "t3_abc123" and post.author == "/u/Researcher"
    assert post.time.hour == 10
    assert "**research**" in post.text and "https://example.org/paper" in post.text
    assert post.metadata["collection_scope"] == "public_atom_feed"
    assert not parse_feed(feed(community="other"), URL)
    assert not parse_feed(feed(), "u/someone_else")
    assert parse_feed(feed(), "u/Researcher")
    assert not parse_feed(feed("<p>[removed]</p>"), URL)
    with pytest.raises(ValidationFailure):
        parse_feed(b"<html>Log in</html>", URL)
    with pytest.raises(ValidationFailure):
        parse_feed(feed(stamp="unknown"), URL)


def test_media_is_limited_to_public_reddit_hosts_and_footer_is_not_content():
    post = parse_feed(
        feed(
            '<!-- SC_OFF --><p>Actual text</p><img src="https://i.redd.it/a.png">'
            '<img src="http://127.0.0.1/a.png"><script>bad()</script>'
            '<!-- SC_ON --> submitted by footer'
        ),
        URL,
    )[0]
    assert post.images == ("https://i.redd.it/a.png",)
    assert "footer" not in post.text and "bad()" not in post.text


def test_registry_checkpoint_dedup_and_changed_content(tmp_path: Path):
    registry = SourcePluginRegistry()
    prepared = registry.prepare(
        {
            "id": "agents-reddit",
            "plugin": "reddit",
            "enabled": True,
            "poll_seconds": 1800,
            "options": {},
            "targets": [{"id": "reddit-fixture", "locator": URL, "name": "Fixture"}],
        },
        config_root=tmp_path,
        runtime_root=tmp_path,
    )
    assert registry.create(prepared).context.options["max_posts_per_target"] == 25

    async def scenario():
        context = SourcePluginContext("agents-reddit", tmp_path, {"max_images_per_post": 0})
        target = PluginTarget("reddit-fixture", URL, "Fixture")
        client = RedditClient()
        first = await collect_public(
            context,
            client,
            CollectRequest(context.source_id, target, {}, NOW),
            parse_feed(feed(), URL),
            "reddit",
        )
        second = await collect_public(
            context,
            client,
            CollectRequest(context.source_id, target, first.checkpoint, NOW),
            parse_feed(feed(), URL),
            "reddit",
        )
        changed = await collect_public(
            context,
            client,
            CollectRequest(context.source_id, target, first.checkpoint, NOW),
            parse_feed(feed("<p>Corrected original</p>"), URL),
            "reddit",
        )
        assert len(first.records) == 1 and not second.records
        assert changed.records[0].record_id == first.records[0].record_id
        assert changed.records[0].occurred_at == first.records[0].occurred_at

    asyncio.run(scenario())


def test_rate_limit_cools_all_targets_without_another_request():
    calls = []

    def request(url, timeout, maximum):
        calls.append(url)
        error = TransientError("HTTP 429")
        error.error_class = ErrorClass.RATE_LIMITED
        raise error

    async def scenario():
        client = RedditClient(request=request)
        with pytest.raises(TransientError):
            await client.posts(URL, time.monotonic() + 20)
        with pytest.raises(TransientError, match="cooling down"):
            await client.posts("r/another", time.monotonic() + 20)
        assert len(calls) == 1 and client.next_request_at > time.monotonic() + 890

    asyncio.run(scenario())


def test_actual_feed_transport_and_denied_access_are_not_silent_success():
    calls = []

    def request(url, timeout, maximum):
        calls.append(url)
        return PublicResponse(feed(), "application/atom+xml", url)

    async def scenario():
        posts = await RedditClient(request=request).posts(URL)
        assert len(posts) == 1 and calls == [URL + "new/.rss?limit=25"]

        def denied(*args):
            raise AuthenticationRequired("HTTP 403")

        with pytest.raises(AuthenticationRequired):
            await RedditClient(request=denied).posts(URL)

    asyncio.run(scenario())
