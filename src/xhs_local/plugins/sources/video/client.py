"""Headless yt-dlp boundary used by YouTube; never opens a browser."""

from __future__ import annotations

import asyncio
import io
import json
import os
import shutil
import signal
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageOps

from xhs_local.core.errors import AuthenticationRequired, TransientError


async def run_command(arguments: list[str], *, timeout: float = 240) -> bytes:
    process = await asyncio.create_subprocess_exec(
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    try:
        output, errors = await asyncio.wait_for(process.communicate(), timeout)
        if process.returncode:
            if b"has been rate-limited by YouTube for up to an hour" in errors:
                raise TransientError(
                    "YouTube temporarily rate-limited this session; retry after one hour",
                    code="YOUTUBE_RATE_LIMITED",
                )
            if b"Sign in to confirm" in errors or b"login required" in errors.lower():
                raise AuthenticationRequired(
                    "video platform requires an authenticated cookies file"
                )
            # Extractor errors can include signed URLs or cookie values; never log them.
            raise TransientError(f"video command failed (exit {process.returncode})")
        return output
    except TimeoutError:
        raise TransientError("video command timed out; saved progress will be retried") from None
    finally:
        if process.returncode is None:
            os.killpg(process.pid, signal.SIGKILL)
            await process.communicate()


class VideoClient:
    def __init__(
        self, *, cookie_file: str | None = None, concurrency: int = 4, node_path=None
    ) -> None:
        self.cookie_file = cookie_file
        self.node_path = node_path
        self.semaphore = asyncio.Semaphore(concurrency)
        self.cooldown_until = 0.0

    @asynccontextmanager
    async def request_slot(self):
        async with self.semaphore:
            if time.monotonic() < self.cooldown_until:
                raise TransientError(
                    "YouTube session is cooling down after a rate limit",
                    code="YOUTUBE_RATE_LIMITED",
                )
            try:
                yield
            except TransientError as error:
                if error.code == "YOUTUBE_RATE_LIMITED":
                    self.cooldown_until = time.monotonic() + 3600
                raise

    def command(self, cookie_file: str | None = None) -> list[str]:
        arguments = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--no-progress",
            "--no-warnings",
            "--no-colors",
            "--socket-timeout",
            "30",
            "--retries",
            "2",
            "--js-runtimes",
            f"node:{self.node_path}" if self.node_path else "node",
            "--ignore-config",
        ]
        if cookie_file:
            arguments.extend(["--cookies", cookie_file])
        return arguments

    async def cookie_path(self):
        return self.cookie_file

    @asynccontextmanager
    async def cookies(self):
        cookie_file = await self.cookie_path()
        if not cookie_file:
            yield None
            return
        # yt-dlp saves cookies on exit: isolated copies prevent concurrent overwrites.
        with tempfile.TemporaryDirectory(prefix="xhs-video-session-") as directory:
            path = Path(directory) / "cookies.txt"
            shutil.copyfile(cookie_file, path)
            path.chmod(0o600)
            yield str(path)

    async def metadata(self, url: str) -> dict[str, Any]:
        async with self.request_slot(), self.cookies() as cookie_file:
            data = await run_command(
                self.command(cookie_file) + ["--skip-download", "--dump-single-json", url]
            )
        return json.loads(data)

    async def audio(
        self, url: str, directory: Path, *, expected_duration: float | None = None
    ) -> Path:
        """Only call after the exact video timestamp has passed the activation boundary."""
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / "audio.mp3"
        if destination.is_file():
            return destination
        completed = directory / "incoming.mp3"
        if completed.is_file() and expected_duration is not None:
            try:
                duration = await self.duration(completed)
                if abs(duration - expected_duration) <= max(3, expected_duration * 0.02):
                    completed.replace(destination)
                    return destination
            except TransientError:
                pass
            completed.unlink()  # Interrupted conversion; keep the resumable source download.
        async with self.request_slot(), self.cookies() as cookie_file:
            await run_command(
                self.command(cookie_file)
                + [
                    "--no-playlist",
                    "-f",
                    "bestaudio/best",
                    "-x",
                    "--audio-format",
                    "mp3",
                    "--audio-quality",
                    "5",
                    "--postprocessor-args",
                    "ExtractAudio+ffmpeg_o:-ac 1",
                    "-o",
                    str(directory / "incoming.%(ext)s"),
                    url,
                ],
                timeout=1800,
            )
        if not completed.is_file():
            raise TransientError("video audio download did not produce a complete file")
        if expected_duration is not None:
            duration = await self.duration(completed)
            if abs(duration - expected_duration) > max(3, expected_duration * 0.02):
                completed.unlink()
                raise TransientError(
                    "audio conversion is incomplete; retained source will be retried"
                )
        completed.replace(destination)
        return destination

    async def duration(self, audio: Path) -> float:
        data = await run_command(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(audio),
            ],
            timeout=30,
        )
        return float(json.loads(data)["format"]["duration"])

    async def images(self, record, metadata: dict, directory: Path) -> list[str]:
        avatar = record.payload.get("avatar_url") or metadata.get("avatar_url")
        headers = {"User-Agent": "Mozilla/5.0", "Referer": record.source_url}
        cover = metadata.get("thumbnail")
        if not avatar or not cover:
            raise TransientError(
                "video creator avatar or cover unavailable; not ready for publication"
            )
        for name, url in (("avatar.png", avatar), ("cover.png", cover)):
            url = url.replace("http://", "https://", 1)
            destination = directory / name
            if destination.exists():
                continue
            try:
                response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=30)
                response.raise_for_status()
            except requests.RequestException:
                raise TransientError("video image download failed") from None
            with Image.open(io.BytesIO(response.content)) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
                temporary = directory / (name + ".tmp")
                image.save(temporary, format="PNG")
                temporary.replace(destination)
        return ["avatar.png", "cover.png"]


def video_entries(info: dict[str, Any]):
    """Channel homepages can contain video, short and archived-live tabs."""
    if info.get("_type") in {"playlist", "multi_video"} or "entries" in info:
        for entry in info.get("entries") or []:
            if isinstance(entry, dict):
                yield from video_entries(entry)
    elif info.get("id"):
        yield info


def channel_avatar(info: dict[str, Any]) -> str | None:
    thumbnails = info.get("thumbnails") or []
    return next(
        (entry["url"] for entry in thumbnails if entry.get("id") == "avatar_uncropped"), None
    )
