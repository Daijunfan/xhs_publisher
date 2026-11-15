from __future__ import annotations

from xhs_local.plugins.contracts import HealthReport, PluginContractError
from xhs_local.plugins.sources.public_content import collect_public

from .client import API, ZhihuClient, locator_kind


class ZhihuSourcePlugin:
    def __init__(self, context, *, request=None):
        self.context = context
        self.client = ZhihuClient(
            timeout=float(context.options.get("request_timeout_seconds", 20)),
            concurrency=int(context.options.get("max_concurrency", 2)),
            **({"request": request} if request else {}),
        )

    @classmethod
    def validate_target(cls, target):
        locator_kind(target.locator)
        if set(target.options) - {"max_items", "include_comments"}:
            raise PluginContractError("Unknown Zhihu target options")

    async def healthcheck(self, target, deadline=None):
        self.validate_target(target)
        if locator_kind(target.locator) != "editorial":
            await self.client.posts(target.locator, deadline)
        value = await self.client.json(API + "/news/latest", deadline)
        return HealthReport(
            ok=True,
            detail={
                "target_id": target.id,
                "public_editorial_items": len(value.get("stories", [])),
                "scope": "public_editorial_selection",
            },
        )

    async def collect(self, request):
        self.validate_target(request.target)
        posts = await self.client.posts(
            request.target.locator,
            request.deadline,
            days=int(self.context.options.get("lookback_days", 3)),
            include_comments=bool(
                request.target.options.get(
                    "include_comments", self.context.options.get("include_comments", True)
                )
            ),
            comment_min_chars=int(self.context.options.get("comment_min_chars", 80)),
        )
        limit = int(
            request.target.options.get(
                "max_items", self.context.options.get("max_posts_per_target", 100)
            )
        )
        return await collect_public(
            self.context,
            self.client,
            request,
            sorted(posts, key=lambda post: post.time, reverse=True)[:limit],
            "zhihu",
        )

    async def close(self):
        return None
