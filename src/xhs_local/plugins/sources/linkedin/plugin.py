from __future__ import annotations

from xhs_local.plugins.contracts import HealthReport, PluginContractError
from xhs_local.plugins.sources.public_content import collect_public

from .client import LinkedInClient, homepage


class LinkedInSourcePlugin:
    def __init__(self, context, *, request=None):
        self.context = context
        self.client = LinkedInClient(
            timeout=float(context.options.get("request_timeout_seconds", 20)),
            concurrency=int(context.options.get("max_concurrency", 2)),
            **({"request": request} if request else {}),
        )

    @classmethod
    def validate_target(cls, target):
        homepage(target.locator)
        if set(target.options) - {"max_items"}:
            raise PluginContractError("Unknown LinkedIn target options")

    async def healthcheck(self, target, deadline=None):
        posts = await self.client.posts(target.locator, deadline)
        return HealthReport(
            ok=True,
            detail={
                "target_id": target.id,
                "public_original_posts": len(posts),
                "scope": "public_guest_page",
            },
        )

    async def collect(self, request):
        self.validate_target(request.target)
        posts = await self.client.posts(request.target.locator, request.deadline)
        limit = int(
            request.target.options.get(
                "max_items", self.context.options.get("max_posts_per_target", 10)
            )
        )
        return await collect_public(
            self.context,
            self.client,
            request,
            sorted(posts, key=lambda post: post.time, reverse=True)[:limit],
            "linkedin",
        )

    async def close(self):
        return None
