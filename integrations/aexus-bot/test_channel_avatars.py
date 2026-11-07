"""Original author extraction and the platform/Core credential boundary, offline."""
import asyncio
import base64
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from channel_avatars import ChannelAuthorAvatars
from channel_content import ChannelContentStore


class AvatarTests(unittest.IsolatedAsyncioTestCase):
    async def test_x_uses_only_the_original_matching_author(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ChannelContentStore(Path(directory))
            try:
                store.execute("asset-put", {"id": "avatar", "data": base64.b64encode(b"original-image").decode(), "mimeType": "image/png"})
                post = {"id": "np_x", "source_id": "author", "avatar_media_id": "avatar", "author_url": "https://x.com/Original", "published_at": 1}
                store.execute("write", {"changes": [{"table": "posts", "key": post["id"], "row": post}]})
                avatars = ChannelAuthorAvatars(None, SimpleNamespace(snapshot=SimpleNamespace(sources=SimpleNamespace(sources=[]))), None, store)
                target = SimpleNamespace(sourceId="author", targetId="target", locator="https://x.com/original")
                self.assertEqual(await avatars._x(target, {}), (b"original-image", "image/png"))
                target.locator = "https://x.com/SomebodyElse"
                self.assertIsNone(await avatars._x(target, {}))
            finally:
                store.close()

    async def test_youtube_uses_a_separate_session_without_core_auth(self):
        stop = asyncio.Event()
        calls, session_options = [], []
        target = SimpleNamespace(enabled=True, plugin="youtube", sourceId="author", locator="https://www.youtube.com/@Original")

        class Response:
            headers = {"content-type": "image/png"}
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            def raise_for_status(self): pass
            async def text(self): return '"channelMetadataRenderer":' + json.dumps({"avatar": {"thumbnails": [{"url": "https://yt3.googleusercontent.com/original"}]}})
            async def read(self): return b"original-youtube-avatar"

        class Session:
            def __init__(self, **kwargs): session_options.append(kwargs)
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            def get(self, url): calls.append(url); return Response()

        class Publisher:
            targets = {"author": target}
            checkpoints = SimpleNamespace(get=lambda *args: None, put=lambda *args: None)
            async def _call(self, command, args):
                self.command, self.args = command, args
                stop.set()

        publisher = Publisher()
        avatars = ChannelAuthorAvatars(publisher, None, None)
        avatars._recent_x = lambda: {}
        with patch("channel_avatars.aiohttp.ClientSession", Session):
            await asyncio.wait_for(avatars.run(stop), 1)
        self.assertEqual(publisher.command, "channel.source-avatar-put")
        self.assertEqual(base64.b64decode(publisher.args["data"]), b"original-youtube-avatar")
        self.assertEqual(len(calls), 2)
        self.assertNotIn("Authorization", session_options[0]["headers"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
