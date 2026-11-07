"""Lazy upload-feed traversal, stopping each tab before its historical pages."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from yt_dlp import YoutubeDL

from xhs_local.core.errors import AuthenticationRequired

from ..video.client import VideoClient, channel_avatar, run_command


def recent_uploads(info: dict, cutoff: float, resolve=None, seen_video_ids=()):
    """Flat discovery only; exact watch metadata belongs to the durable plugin batch."""
    known = set(seen_video_ids)
    undated = 0
    for entry in info.get("entries") or ():
        if not isinstance(entry, dict):
            continue
        if "entries" in entry:
            yield from recent_uploads(entry, cutoff, seen_video_ids=known)
            continue
        timestamp = entry.get("timestamp")
        if timestamp and timestamp < cutoff and entry.get("live_status") not in {"is_live", "is_upcoming"}:
            break
        if not entry.get("id") or entry["id"] in known:
            continue
        if not timestamp:
            undated += 1
            if undated > 30:
                break
        yield {key: entry.get(key) for key in (
            "id", "title", "timestamp", "release_timestamp", "duration",
            "uploader", "uploader_id", "channel_id", "live_status", "video_metadata",
        )}


class YouTubeClient(VideoClient):
    def __init__(self, *, cookie_file=None, chrome_profile=None, runtime_root=None, node_path=None):
        if cookie_file and chrome_profile:
            raise ValueError("choose either cookie_file or chrome_profile")
        super().__init__(cookie_file=cookie_file, node_path=node_path)
        self.chrome_profile = chrome_profile
        self.runtime_root = Path(runtime_root) if runtime_root else None

    def command(self, cookie_file: str | None = None) -> list[str]:
        return super().command(cookie_file) + [
            "--sleep-requests", "0.75", "--sleep-interval", "10", "--max-sleep-interval", "20"
        ]

    async def cookie_path(self):
        if self.chrome_profile:
            from .session import session_file

            return await session_file(self.chrome_profile, self.runtime_root)
        return self.cookie_file

    async def _refresh_session(self):
        if not self.chrome_profile:
            raise AuthenticationRequired("YouTube cookies need renewal")
        from .session import session_file

        await session_file(self.chrome_profile, self.runtime_root, force=True)

    async def metadata(self, url: str) -> dict:
        try:
            return await super().metadata(url)
        except AuthenticationRequired:
            await self._refresh_session()
            return await super().metadata(url)

    async def audio(self, url: str, directory: Path, *, expected_duration=None) -> Path:
        try:
            return await super().audio(url, directory, expected_duration=expected_duration)
        except AuthenticationRequired:
            await self._refresh_session()
            return await super().audio(url, directory, expected_duration=expected_duration)

    async def images(self, record, metadata: dict, directory: Path) -> list[str]:
        if not record.payload.get("avatar_url") and not metadata.get("avatar_url"):
            about = await self.metadata(record.payload["creator_url"].rstrip("/") + "/about")
            metadata = {**metadata, "avatar_url": channel_avatar(about)}
        return await super().images(record, metadata, directory)

    async def discover(self, homepage: str, activated_at: datetime, seen_video_ids=()) -> dict:
        arguments = [
            sys.executable,
            "-m",
            "xhs_local.plugins.sources.youtube.client",
            homepage,
            str((activated_at - timedelta(days=7)).timestamp()),
        ]
        async with self.request_slot(), self.cookies() as cookie_file:
            arguments.extend([cookie_file or "-", str(self.node_path or "-"), json.dumps(sorted(seen_video_ids))])
            return json.loads(await run_command(arguments, timeout=60))


def discover_uploads(
    homepage: str, cutoff: float, cookie_file: str | None = None, node_path=None, seen_video_ids=()
) -> dict:
    options = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "sleep_interval_requests": 0.75,
        "sleep_interval": 10,
        "max_sleep_interval": 20,
        "ignore_no_formats_error": True,
        "js_runtimes": {"node": {"path": node_path} if node_path else {}},
        "extractor_args": {"youtubetab": {"approximate_date": ["true"]}},
    }
    if cookie_file:
        options["cookiefile"] = cookie_file
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(homepage, download=False, process=False)
        return {
            "id": info.get("id"),
            "channel_id": info.get("channel_id"),
            "uploader": info.get("uploader"),
            "thumbnails": info.get("thumbnails", []),
            # VideoSourcePlugin skips seen IDs before requesting full metadata.
            "entries": list(recent_uploads(info, cutoff, seen_video_ids=seen_video_ids)),
        }


if __name__ == "__main__":
    print(
        json.dumps(
            discover_uploads(
                sys.argv[1],
                float(sys.argv[2]),
                sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None,
                sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None,
                json.loads(sys.argv[5]) if len(sys.argv) > 5 else (),
            )
        )
    )
