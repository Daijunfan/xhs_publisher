"""YouTube creator source using the shared video discovery contract."""

from ..video.plugin import VideoSourcePlugin
from .client import YouTubeClient


class YouTubeSourcePlugin(VideoSourcePlugin):
    platform = "youtube"

    def __init__(self, context, *, client=None):
        super().__init__(
            context,
            client=client
            or YouTubeClient(
                cookie_file=context.options.get("cookie_file"),
                chrome_profile=context.options.get("chrome_profile"),
                runtime_root=context.runtime_root,
                node_path=context.options.get("node_path"),
            ),
        )
