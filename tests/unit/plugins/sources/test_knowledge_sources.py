from __future__ import annotations

import asyncio
import json
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from xhs_local.configuration.knowledge_sources import linkedin_homepage, zhihu_locator_kind
from xhs_local.core.errors import AuthenticationRequired, TransientError, ValidationFailure
from xhs_local.plugins.contracts import (
    CollectRequest,
    PluginTarget,
    SourcePlugin,
    SourcePluginContext,
)
from xhs_local.plugins.registry import SourcePluginRegistry
from xhs_local.plugins.sources.linkedin.client import informative, parse_page
from xhs_local.plugins.sources.public_content import (
    PublicClient,
    PublicPost,
    PublicRedirect,
    PublicResponse,
    collect_public,
    public_request,
)
from xhs_local.plugins.sources.zhihu.client import ZhihuClient, parse_story, valuable_comment

NOW = datetime(2026, 11, 15, 12, tzinfo=UTC)
PROFILE = "https://www.linkedin.com/company/fixture-research"


@pytest.mark.parametrize(
    ("plugin", "locator"), [("zhihu", "https://daily.zhihu.com/"), ("linkedin", PROFILE)]
)
def test_plugins_load_through_the_existing_registry(tmp_path, plugin, locator):
    registry = SourcePluginRegistry()
    prepared = registry.prepare(
        {
            "id": "fixture-" + plugin,
            "plugin": plugin,
            "enabled": True,
            "poll_seconds": 1800,
            "options": {},
            "targets": [{"id": "fixture", "name": "Fixture", "locator": locator}],
        },
        config_root=tmp_path,
        runtime_root=tmp_path,
    )
    instance = registry.create(prepared)
    assert isinstance(instance, SourcePlugin)
    if plugin == "linkedin":
        assert prepared.context.options["lookback_hours"] == 2160
    assert asyncio.run(registry.preflight(prepared)).ok
    asyncio.run(instance.close())


def test_public_locators_keep_identity_and_reject_non_profiles():
    assert (
        linkedin_homepage(
            "https://uk.linkedin.com/showcase/microsoftresearch/?originalSubdomain=uk"
        )
        == "https://www.linkedin.com/showcase/microsoftresearch"
    )
    assert linkedin_homepage(PROFILE + "/posts/?feedView=all") == PROFILE
    assert zhihu_locator_kind("https://daily.zhihu.com/") == "editorial"
    assert zhihu_locator_kind("https://www.zhihu.com/people/fixture/answers") == "author"
    for url in [
        "https://evil.example/company/fixture",
        "https://user:password@linkedin.com/company/fixture",
        "https://www.linkedin.com/posts/id",
        "https://www.linkedin.com:999/company/fixture",
    ]:
        with pytest.raises(ValueError):
            linkedin_homepage(url)


def test_linkedin_uses_original_author_and_exact_publication_not_discovery_time():
    def entry(id, *, author=PROFILE, stamp="2026-11-14T16:01:46.556Z", text=None):
        return {
            "@type": "SocialMediaPosting",
            "author": {"name": "Fixture Research", "url": author},
            "datePublished": stamp,
            "url": "https://www.linkedin.com/posts/fixture-research_results-activity-"
            + id
            + "-test",
            "text": text or "A new research paper reports a reproducible analysis. " * 8,
        }

    html = (
        '<article data-activity-urn="urn:li:activity:123">'
        '<img data-delayed-url="https://media.licdn.com/dms/image/company-logo/avatar">'
        '<img data-delayed-url="https://media.licdn.com/dms/image/article/photo"></article>'
    )
    html += (
        '<script type="application/ld+json">'
        + json.dumps(
            {
                "@graph": [
                    entry("123"),
                    entry("124", author="https://www.linkedin.com/company/other"),
                    entry("125", stamp=""),
                    entry("126", text="Join our team! Apply now! " * 10),
                ]
            }
        )
        + "</script>"
    )
    posts = parse_page(html.encode(), PROFILE)
    assert len(posts) == 1
    assert posts[0].id == "123"
    assert posts[0].time == datetime(2026, 11, 14, 16, 1, 46, 556000, tzinfo=UTC)
    assert posts[0].images == ("https://media.licdn.com/dms/image/article/photo",)
    assert posts[0].avatar.endswith("avatar")
    assert not informative("Excellent! Follow and subscribe.")


@pytest.mark.parametrize("status", [401, 403, 999])
def test_access_restrictions_never_trigger_an_alternate_request(status):
    calls = []

    class Opener:
        def open(self, request, **kwargs):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, status, "restricted", {}, None)

    with (
        patch("urllib.request.build_opener", return_value=Opener()),
        pytest.raises(AuthenticationRequired),
    ):
        public_request(PROFILE, 1, 1000)
    assert calls == [PROFILE]


def test_private_redirect_is_rejected_before_following():
    import urllib.request

    with pytest.raises(ValidationFailure):
        PublicRedirect().redirect_request(
            urllib.request.Request(PROFILE), None, 302, "", {}, "http://127.0.0.1/admin"
        )


def story():
    return {
        "id": 42,
        "title": "A concrete public question",
        "body": '<div class="answer"><div class="meta">'
        '<span class="author">Author One，</span><a class="originUrl" hidden '
        'href="https://www.zhihu.com/question/1/answer/99">原文</a></div>'
        '<div class="content"><p>'
        + "具体原理及其证据，需要区分事实与推测。" * 20
        + "</p></div></div>",
    }


def test_zhihu_retains_authorship_original_link_and_honest_date_basis():
    post = parse_story(story(), "20261115")[0]
    assert post.id == "answer:99"
    assert post.author == "Author One"
    assert post.url.endswith("/answer/99")
    assert post.time == datetime(2026, 11, 14, 16, tzinfo=UTC)
    assert post.metadata["time_basis"] == "editorial_selection_date"
    assert post.metadata["time_precision"] == "day"
    assert "知乎日报精选" in post.text and "知乎原文" in post.text
    assert not valuable_comment("赞！精彩！")
    assert not valuable_comment("私信咨询，免费领取" * 30, 99)
    assert valuable_comment("补充一个需要区分的原因：" + "这里有实证与机制上的差别。" * 15)


def test_public_comments_keep_parent_context_and_their_own_time():
    async def scenario():
        content = "补充一个原因：" + "这份研究的样本与因果机制值得区分。" * 12
        responses = {
            "/news/latest": {"date": "20261115", "stories": [{"id": 42}]},
            "/news/42": story(),
            "/story/42/long-comments": {
                "comments": [
                    {
                        "id": 123,
                        "author": "Comment Author",
                        "content": content,
                        "time": int(NOW.timestamp()) - 60,
                        "likes": 0,
                        "reply_to": {"author": "Prior author", "content": "A public prior remark"},
                    }
                ]
            },
            "/story/42/short-comments": {
                "comments": [
                    {
                        "id": 124,
                        "author": "Short",
                        "content": "点赞",
                        "time": int(NOW.timestamp()),
                        "likes": 20,
                    }
                ]
            },
        }

        def fetch(url, timeout, maximum):
            return PublicResponse(
                json.dumps(responses[url.split("/api/4", 1)[1]]).encode(), url=url
            )

        posts = await ZhihuClient(request=fetch).posts("https://daily.zhihu.com/", days=1)
        comment = next(post for post in posts if post.id == "comment:123")
        assert comment.time == NOW - timedelta(minutes=1)
        assert "A concrete public question" in comment.text
        assert "A public prior remark" in comment.text
        assert all(post.id != "comment:124" for post in posts)
        with pytest.raises(AuthenticationRequired):
            await ZhihuClient(request=fetch).posts("https://www.zhihu.com/people/fixture")

    asyncio.run(scenario())


def test_checkpoint_dedupes_unchanged_work_and_filters_future_items(tmp_path: Path):
    async def scenario():
        target = PluginTarget("fixture", PROFILE, "Fixture")
        context = SourcePluginContext("linkedin-fixture", tmp_path, {"max_images_per_post": 0})
        request = CollectRequest(context.source_id, target, {}, NOW)
        post = PublicPost(
            "1", NOW - timedelta(minutes=1), "Actual public text", "Title", PROFILE, "Author"
        )
        first = await collect_public(
            context,
            PublicClient(("linkedin.com",)),
            request,
            [
                post,
                PublicPost(
                    "future", NOW + timedelta(days=1), "Future", "Future", PROFILE, "Author"
                ),
            ],
            "linkedin",
        )
        assert [record.external_id for record in first.records] == ["1"]
        second = await collect_public(
            context,
            PublicClient(("linkedin.com",)),
            CollectRequest(context.source_id, target, first.checkpoint, NOW),
            [post],
            "linkedin",
        )
        assert second.records == ()

    asyncio.run(scenario())


def test_incomplete_media_keeps_text_and_retries_before_checkpointing(tmp_path):
    async def scenario():
        calls = []

        def fetch(url, timeout, maximum):
            calls.append(url)
            if len(calls) == 1:
                raise TransientError("Network unavailable")
            return PublicResponse(b"fixture-image", "image/png", url)

        context = SourcePluginContext("linkedin-fixture", tmp_path, {})
        target = PluginTarget("fixture", PROFILE, "Fixture")
        post = PublicPost(
            "partial",
            NOW,
            "Original text survives a media error",
            "Title",
            PROFILE,
            "Author",
            images=("https://media.licdn.com/photo.png",),
        )
        client = PublicClient(("linkedin.com", "licdn.com"), request=fetch)
        first = await collect_public(
            context, client, CollectRequest(context.source_id, target, {}, NOW), [post], "linkedin"
        )
        assert first.records[0].text == post.text and first.errors == 1
        assert post.id not in first.checkpoint["fingerprints"]
        second = await collect_public(
            context,
            client,
            CollectRequest(context.source_id, target, first.checkpoint, NOW),
            [post],
            "linkedin",
        )
        assert second.errors == 0 and len(second.records[0].attachments) == 1
        third = await collect_public(
            context,
            client,
            CollectRequest(context.source_id, target, second.checkpoint, NOW),
            [post],
            "linkedin",
        )
        assert third.records == () and len(calls) == 2

    asyncio.run(scenario())


def test_unsupported_media_keeps_text_without_repeated_downloads(tmp_path):
    async def scenario():
        calls = []

        def fetch(url, timeout, maximum):
            calls.append(url)
            raise ValidationFailure("Public source response exceeds its size limit")

        context = SourcePluginContext("linkedin-fixture", tmp_path, {})
        target = PluginTarget("fixture", PROFILE, "Fixture")
        post = PublicPost(
            "oversize",
            NOW,
            "Original text remains available",
            "Title",
            PROFILE,
            "Author",
            images=("https://media.licdn.com/large.gif",),
        )
        client = PublicClient(("linkedin.com", "licdn.com"), request=fetch)
        first = await collect_public(
            context, client, CollectRequest(context.source_id, target, {}, NOW), [post], "linkedin"
        )
        assert first.records[0].text == post.text and first.errors == 1
        assert first.records[0].payload["image_urls"] == list(post.images)
        second = await collect_public(
            context,
            client,
            CollectRequest(context.source_id, target, first.checkpoint, NOW),
            [post],
            "linkedin",
        )
        assert not second.records and len(calls) == 1

    asyncio.run(scenario())
