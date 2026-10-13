"""Bounded, credential-free X SourcePlugin."""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, timedelta
from typing import Any

from xhs_local.core.contracts import CollectBatch
from xhs_local.plugins.contracts import (
    CollectRequest,
    HealthReport,
    PluginContractError,
    PluginTarget,
    SourcePluginContext,
)

from .client import Request, XPublicClient
from .mapper import map_post

HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,15}$")


class XSourcePlugin:
    def __init__(
        self,
        context: SourcePluginContext,
        *,
        request: Request | None = None,
    ) -> None:
        self.context = context
        options = context.options
        self.lookback_hours = float(options["lookback_hours"])
        self.max_posts_per_target = int(options["max_posts_per_target"])
        self.max_images_per_post = int(options["max_images_per_post"])
        dependencies: dict[str, Any] = {}
        if request is not None:
            dependencies["request"] = request
        self.client = XPublicClient(
            request_timeout_seconds=float(options["request_timeout_seconds"]),
            max_image_bytes=int(options["max_image_bytes"]),
            max_concurrency=int(options["max_concurrency"]),
            **dependencies,
        )

    @classmethod
    def validate_target(cls, target: PluginTarget) -> None:
        handle = target.locator.removeprefix("@").strip()
        if not target.id.strip() or not target.name.strip():
            raise PluginContractError("X target id/name must be non-empty")
        if not HANDLE_PATTERN.fullmatch(handle):
            raise PluginContractError(f"X target {target.id} locator must be an account handle")
        unknown = set(target.options) - {"max_items"}
        if unknown:
            raise PluginContractError(
                f"X target {target.id} has unknown options: {', '.join(sorted(unknown))}"
            )
        max_items = target.options.get("max_items")
        if max_items is not None and (
            isinstance(max_items, bool) or not isinstance(max_items, int) or max_items < 1
        ):
            raise PluginContractError(f"X target {target.id} max_items must be positive")

    async def healthcheck(
        self,
        target: PluginTarget,
        deadline: float | None = None,
    ) -> HealthReport:
        self.validate_target(target)
        posts = await self.client.fetch_profile(target.locator, deadline=deadline)
        return HealthReport(
            ok=True,
            detail={"target_id": target.id, "public_posts": len(posts)},
        )

    async def collect(self, request: CollectRequest) -> CollectBatch:
        if request.source_id != self.context.source_id:
            raise PluginContractError("CollectRequest source_id does not match plugin context")
        self.validate_target(request.target)
        request.ensure_active()
        observed_at = request.observed_at
        if observed_at.tzinfo is None:
            raise PluginContractError("CollectRequest observed_at must include timezone")
        observed_at = observed_at.astimezone(UTC)
        posts = await self.client.fetch_profile(
            request.target.locator,
            deadline=request.deadline,
        )
        cutoff = observed_at - timedelta(hours=self.lookback_hours)
        limit = int(request.target.options.get("max_items", self.max_posts_per_target))
        eligible = [post for post in posts if cutoff <= post.created_at <= observed_at][:limit]
        records = []
        errors = 0
        avatar = None
        avatar_url = next((post.avatar_url for post in eligible if post.avatar_url), None)
        try:
            if avatar_url is None:
                avatar_url = await self.client.fetch_avatar_url(
                    request.target.locator,
                    deadline=request.deadline,
                )
            if avatar_url is not None:
                avatar = await self.client.download_image(
                    avatar_url,
                    post_id=request.target.locator.removeprefix("@"),
                    index=0,
                    deadline=request.deadline,
                )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            errors += 1
            self.context.log(
                "x_avatar_error",
                {
                    "source_id": request.source_id,
                    "target_id": request.target.id,
                    "error": " ".join(str(error).split())[:300],
                },
            )
        for post in eligible:
            request.ensure_active()
            images = []
            for index, url in enumerate(post.image_urls[: self.max_images_per_post], start=1):
                try:
                    images.append(
                        await self.client.download_image(
                            url,
                            post_id=post.post_id,
                            index=index,
                            deadline=request.deadline,
                        )
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    errors += 1
                    self.context.log(
                        "x_media_error",
                        {
                            "source_id": request.source_id,
                            "target_id": request.target.id,
                            "post_id": post.post_id,
                            "error": " ".join(str(error).split())[:300],
                        },
                    )
            records.append(
                map_post(
                    post,
                    source_id=request.source_id,
                    target=request.target,
                    observed_at=observed_at,
                    avatar=avatar,
                    images=tuple(images),
                )
            )
        records.sort(key=lambda record: (record.occurred_at, int(record.external_id)))
        return CollectBatch(
            source_id=request.source_id,
            target_id=request.target.id,
            records=tuple(records),
            checkpoint={},
            messages_seen=len(posts),
            errors=errors,
        )

    async def close(self) -> None:
        return None
