from __future__ import annotations

from xhs_local.configuration.knowledge_sources import reddit_homepage
from xhs_local.plugins.contracts import HealthReport
from xhs_local.plugins.sources.public_content import collect_public

from .client import RedditClient


class RedditSourcePlugin:
    def __init__(self, context, *, request=None):
        self.context = context
        self.client = RedditClient(
            timeout=float(context.options.get("request_timeout_seconds", 20)),
            concurrency=1,
            **({"request": request} if request else {}),
        )

    @classmethod
    def validate_target(cls, target):
        reddit_homepage(target.locator)

    async def healthcheck(self, target, deadline=None):
        posts = await self.client.posts(target.locator, deadline, 5)
        return HealthReport(
            ok=True,
            detail={"target_id": target.id, "posts": len(posts), "scope": "public_atom_feed"},
        )

    async def collect(self, request):
        self.validate_target(request.target)
        posts = await self.client.posts(
            request.target.locator,
            request.deadline,
            int(self.context.options.get("max_posts_per_target", 25)),
        )
        return await collect_public(self.context, self.client, request, posts, "reddit")

    async def close(self):
        return None
