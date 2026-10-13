from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from xhs_local.plugins.contracts import (
    CollectRequest,
    PluginContractError,
    PluginTarget,
    SourcePluginContext,
)
from xhs_local.plugins.sources.x.client import (
    HttpResponse,
    XPublicClient,
    parse_profile_avatar,
    parse_profile_html,
    parse_profile_statuses,
)
from xhs_local.plugins.sources.x.plugin import XSourcePlugin

NOW = datetime(2026, 8, 27, 2, 0, tzinfo=UTC)


def article(
    post_id: str,
    created_at: datetime,
    *,
    handle: str = "karpathy",
    name: str = "Andrej Karpathy",
    text: str = "A concrete update about language model research.",
    media: str = "",
) -> str:
    timestamp = created_at.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return f"""
<article itemID="https://x.com/{handle}/status/{post_id}" itemType="https://schema.org/SocialMediaPosting">
  <meta content="{post_id}" itemProp="identifier"/>
  <meta content="{timestamp}" itemProp="datePublished"/>
  <meta content="{text}" itemProp="text"/>
  <div itemProp="author">
    <meta content="{name}" itemProp="name"/>
    <meta content="{handle}" itemProp="alternateName"/>
  </div>
  {media}
</article>
"""


def profile_html() -> str:
    quoted = article(
        "900",
        NOW - timedelta(minutes=10),
        handle="other_author",
        name="Other Author",
    )
    recent = article(
        "101",
        NOW - timedelta(hours=1),
        media=(
            '<img src="https://pbs.twimg.com/profile_images/avatar.jpg"/>'
            '<img src="https://pbs.twimg.com/media/photo-one?format=webp&amp;name=medium"/>'
            '<meta content="https://pbs.twimg.com/media/photo-one.jpg" itemProp="image"/>'
            f"{quoted}"
        ),
    )
    old = article("100", NOW - timedelta(hours=25), text="An old post outside the window.")
    return (
        "<!doctype html><html><head><title>Andrej Karpathy (@karpathy) / X</title></head>"
        f"<body>{recent}{old}</body></html>"
    )


def profile_statuses(*, include_avatar: bool = True) -> bytes:
    def status(
        post_id: str,
        created_at: datetime,
        *,
        handle: str = "karpathy",
        name: str = "Andrej Karpathy",
        text: str = "A concrete update about language model research.",
        media: list[dict[str, object]] | None = None,
        reposted_by: dict[str, str] | None = None,
    ) -> dict[str, object]:
        return {
            "type": "status",
            "id": post_id,
            "url": f"https://x.com/{handle}/status/{post_id}",
            "text": text,
            "created_timestamp": int(created_at.timestamp()),
            "author": {
                "screen_name": handle,
                "name": name,
                "avatar_url": (
                    "https://pbs.twimg.com/profile_images/avatar.jpg" if include_avatar else ""
                ),
            },
            "media": {"all": media or []},
            "reposted_by": reposted_by,
        }

    payload = {
        "code": 200,
        "results": [
            status("900", NOW - timedelta(minutes=10), handle="other_author"),
            status(
                "102",
                NOW - timedelta(minutes=20),
                handle="research_author",
                reposted_by={
                    "screen_name": "karpathy",
                    "name": "Andrej Karpathy",
                    "avatar_url": (
                        "https://pbs.twimg.com/profile_images/avatar.jpg" if include_avatar else ""
                    ),
                },
            ),
            status(
                "101",
                NOW - timedelta(hours=1),
                media=[
                    {
                        "type": "photo",
                        "url": "https://pbs.twimg.com/media/photo-one.jpg?name=orig",
                    }
                ],
            ),
            status("100", NOW - timedelta(hours=25), text="An old post outside the window."),
        ],
        "cursor": {"top": None, "bottom": None},
    }
    return json.dumps(payload).encode()


def test_public_profile_parser_extracts_author_text_time_and_unique_media() -> None:
    posts = parse_profile_html(profile_html(), "karpathy")

    assert [post.post_id for post in posts] == ["100", "101"]
    recent = posts[1]
    assert recent.author_name == "Andrej Karpathy"
    assert recent.author_handle == "karpathy"
    assert recent.avatar_url == "https://pbs.twimg.com/profile_images/avatar.jpg"
    assert recent.text == "A concrete update about language model research."
    assert recent.image_urls == ("https://pbs.twimg.com/media/photo-one?format=webp&name=medium",)


def test_public_timeline_parser_extracts_current_json_statuses() -> None:
    posts = parse_profile_statuses(profile_statuses(), "karpathy")

    assert [post.post_id for post in posts] == ["100", "101", "102"]
    assert posts[2].author_handle == "karpathy"
    assert posts[1].author_name == "Andrej Karpathy"
    assert posts[1].avatar_url == "https://pbs.twimg.com/profile_images/avatar.jpg"
    assert posts[1].image_urls == ("https://pbs.twimg.com/media/photo-one.jpg?name=orig",)


def _plugin(
    tmp_path: Path,
    *,
    fail_media: bool = False,
    no_html_avatar: bool = False,
    logs=None,
) -> XSourcePlugin:
    def request(url: str, _timeout: float, _maximum: int) -> HttpResponse:
        if url.endswith("/statuses"):
            return HttpResponse(
                profile_statuses(include_avatar=not no_html_avatar),
                "application/json",
            )
        if url.startswith("https://x.com/"):
            html = profile_html()
            if no_html_avatar:
                html = html.replace(
                    '<img src="https://pbs.twimg.com/profile_images/avatar.jpg"/>',
                    "",
                )
            return HttpResponse(html.encode(), "text/html; charset=UTF-8")
        if url.startswith("https://api.fxtwitter.com/"):
            return HttpResponse(
                json.dumps(
                    {
                        "code": 200,
                        "user": {
                            "screen_name": "karpathy",
                            "avatar_url": "https://pbs.twimg.com/profile_images/fallback.jpg",
                        },
                    }
                ).encode(),
                "application/json",
            )
        if fail_media and "/media/" in url:
            raise RuntimeError("media unavailable")
        return HttpResponse(b"RIFF\x00\x00\x00\x00WEBPimage", "image/webp")

    context = SourcePluginContext(
        source_id="x-main",
        runtime_root=tmp_path,
        options={
            "lookback_hours": 24,
            "max_posts_per_target": 10,
            "max_images_per_post": 4,
            "max_image_bytes": 20 * 1024 * 1024,
            "request_timeout_seconds": 30,
            "max_concurrency": 2,
        },
        log=(lambda event, fields: logs.append((event, fields)))
        if logs is not None
        else lambda *_args: None,
    )
    return XSourcePlugin(context, request=request)


def test_collect_is_stateless_limits_to_24_hours_and_marks_original_author(tmp_path: Path) -> None:
    plugin = _plugin(tmp_path)
    target = PluginTarget("x-karpathy", "karpathy", "Andrej Karpathy @karpathy")
    request = CollectRequest(
        source_id="x-main",
        target=target,
        checkpoint={"ignored": "plugin owns no state"},
        observed_at=NOW,
    )

    first = asyncio.run(plugin.collect(request))
    second = asyncio.run(plugin.collect(request))

    assert first.checkpoint == {}
    assert second.checkpoint == {}
    assert [record.external_id for record in first.records] == ["101", "102"]
    record = first.records[0]
    assert record.plugin_id == "x"
    assert record.content_type == "tech_news"
    assert record.source_name == "Andrej Karpathy @karpathy"
    assert record.source_url == "https://x.com/karpathy/status/101"
    assert record.payload["author_handle"] == "karpathy"
    assert record.payload["avatar_attachment_index"] == 0
    assert len(record.attachments) == 2
    assert all(attachment.mime_type == "image/webp" for attachment in record.attachments)
    assert second.records[0].record_id == record.record_id


def test_media_failure_keeps_text_record_and_healthcheck_is_read_only(tmp_path: Path) -> None:
    logs = []
    plugin = _plugin(tmp_path, fail_media=True, logs=logs)
    target = PluginTarget("x-karpathy", "@karpathy", "Andrej Karpathy @karpathy")

    health = asyncio.run(plugin.healthcheck(target))
    batch = asyncio.run(
        plugin.collect(
            CollectRequest(
                source_id="x-main",
                target=target,
                checkpoint={},
                observed_at=NOW,
            )
        )
    )

    assert health.ok is True
    assert health.detail["public_posts"] == 3
    assert len(batch.records[0].attachments) == 1
    assert batch.records[0].payload["avatar_attachment_index"] == 0
    assert batch.errors == 1
    assert logs[0][0] == "x_media_error"


def test_missing_html_avatar_uses_verified_public_profile_fallback(tmp_path: Path) -> None:
    plugin = _plugin(tmp_path, no_html_avatar=True)
    target = PluginTarget("x-karpathy", "karpathy", "Andrej Karpathy @karpathy")

    batch = asyncio.run(
        plugin.collect(
            CollectRequest(
                source_id="x-main",
                target=target,
                checkpoint={},
                observed_at=NOW,
            )
        )
    )

    assert batch.records[0].payload["avatar_attachment_index"] == 0
    assert batch.records[0].attachments[0].file_name == "x-karpathy-0.webp"


def test_profile_avatar_parser_rejects_handle_mismatch() -> None:
    body = json.dumps(
        {
            "code": 200,
            "user": {
                "screen_name": "other",
                "avatar_url": "https://pbs.twimg.com/profile_images/avatar.jpg",
            },
        }
    ).encode()

    with pytest.raises(RuntimeError, match="does not match"):
        parse_profile_avatar(body, "karpathy")


def test_target_validation_rejects_urls_and_invalid_options(tmp_path: Path) -> None:
    plugin = _plugin(tmp_path)
    with pytest.raises(PluginContractError, match="account handle"):
        plugin.validate_target(PluginTarget("x-bad", "https://x.com/karpathy", "Bad"))
    with pytest.raises(PluginContractError, match="unknown options"):
        plugin.validate_target(PluginTarget("x-bad", "karpathy", "Bad", {"history": 1}))


def test_client_enforces_response_limit(tmp_path: Path) -> None:
    del tmp_path
    requested: list[str] = []

    def request(url: str, _timeout: float, maximum: int) -> HttpResponse:
        requested.append(url)
        assert maximum > 0
        return HttpResponse(profile_statuses(), "application/json")

    client = XPublicClient(
        request_timeout_seconds=30,
        max_image_bytes=1024,
        max_concurrency=1,
        request=request,
    )
    posts = asyncio.run(client.fetch_profile("karpathy", deadline=None))
    assert len(posts) == 3
    assert requested == ["https://api.fxtwitter.com/2/profile/karpathy/statuses"]
