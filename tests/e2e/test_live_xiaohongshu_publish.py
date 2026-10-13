from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

import pytest

from xhs_local.core.contracts import PublishNote
from xhs_local.plugins.sinks.xiaohongshu.browser import SafariPublisher, SafariSession
from xhs_local.rendering.renderer import HtmlPhotoGenerator

LIVE_ENABLED = os.environ.get("XHS_LIVE_PUBLISH") == "1"


@pytest.mark.skipif(not LIVE_ENABLED, reason="requires XHS_LIVE_PUBLISH=1")
def test_stable_safari_backend_publishes_and_confirms_hello_world() -> None:
    async def scenario() -> None:
        with tempfile.TemporaryDirectory(prefix="xhs-live-publish-") as temporary:
            image = await HtmlPhotoGenerator(output_dir=Path(temporary)).generate_single_photo(
                "hello world",
                filename="hello-world.png",
                headline="hello world",
                source="publish interface test",
                posted_at="2026-08-28T16:00:00+08:00",
                variant=1,
            )
            publisher = SafariPublisher(
                max_images=18,
                background=True,
                keep_window_open=False,
                session=SafariSession(background=True, persistent=False),
            )
            try:
                result = await publisher.publish(
                    PublishNote("你好", "你好", (image,)),
                    require_new_title_occurrence=True,
                )
            finally:
                await publisher.close()

        assert result.ok is True
        assert result.confirmed_in_note_manager is True
        print(
            json.dumps(
                {"title": "你好", "body": "你好", "confirmed": True},
                ensure_ascii=False,
            )
        )

    asyncio.run(scenario())
