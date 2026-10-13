"""Explicit Chrome profile; only YouTube cookies are retained in runtime/secrets."""

from __future__ import annotations

import asyncio
import hashlib
import sys
import tempfile
import time
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.cookies import YDLLogger, YoutubeDLCookieJar, extract_cookies_from_browser

from ..video.client import run_command

_locks: dict[Path, asyncio.Lock] = {}


def export_session(profile: str, destination: Path) -> None:
    with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        browser = extract_cookies_from_browser("chrome", profile=profile, logger=YDLLogger(ydl))
    selected = YoutubeDLCookieJar(str(destination))
    for cookie in browser:
        if cookie.domain.lstrip(".") == "youtube.com" or cookie.domain.endswith(".youtube.com"):
            selected.set_cookie(cookie)
    if not any(cookie.name in {"SID", "SAPISID", "__Secure-3PAPISID"} for cookie in selected):
        raise RuntimeError("YouTube login required, or Chrome Keychain access was denied")
    selected.save()
    destination.chmod(0o600)


async def session_file(profile: str, runtime_root: Path, *, force: bool = False) -> Path:
    path = (
        runtime_root
        / "secrets"
        / f"youtube-browser-{hashlib.sha256(profile.encode()).hexdigest()[:12]}.txt"
    )
    async with _locks.setdefault(path, asyncio.Lock()):
        if not force and path.is_file() and time.time() - path.stat().st_mtime < 1800:
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".youtube-session-", delete=False
        ) as stream:
            temporary = Path(stream.name)
        try:
            await run_command(
                [
                    sys.executable,
                    "-m",
                    "xhs_local.plugins.sources.youtube.session",
                    profile,
                    str(temporary),
                ],
                timeout=30,
            )
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        return path


if __name__ == "__main__":
    export_session(sys.argv[1], Path(sys.argv[2]))
