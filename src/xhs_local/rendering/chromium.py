"""Headless Chromium discovery, capture, and PNG verification."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import struct
import sys
import time
from collections.abc import Sequence
from pathlib import Path

SCREENSHOT_TIMEOUT_SECONDS = 30.0
KILL_GRACE_SECONDS = 2.0
STABLE_CHECKS_REQUIRED = 4
POLL_SECONDS = 0.05

BROWSER_CANDIDATES = {
    "darwin": (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ),
    "linux": (
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ),
    "win32": (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ),
}


def _executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def find_browser(explicit_path: str | Path | None = None) -> Path:
    """Return an executable Chromium-family browser path."""

    if explicit_path:
        path = Path(explicit_path).expanduser().resolve()
        if _executable(path):
            return path
        raise RuntimeError(f"HTML photo browser is not executable: {path}")
    for candidate in BROWSER_CANDIDATES.get(sys.platform, ()):
        path = Path(candidate)
        if _executable(path):
            return path
    raise RuntimeError(
        "Google Chrome, Chromium, or Microsoft Edge is required. "
        "Set HTML_PHOTO_BROWSER_PATH to the browser executable."
    )


def screenshot_args(
    *,
    width: int,
    height: int,
    profile_dir: Path,
    screenshot_path: Path | None,
    page_url: str,
) -> tuple[str, ...]:
    return (
        "--headless=new",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-gpu",
        "--disable-sync",
        "--hide-scrollbars",
        "--metrics-recording-only",
        "--no-first-run",
        "--password-store=basic",
        "--use-mock-keychain",
        "--force-device-scale-factor=1",
        f"--user-data-dir={profile_dir}",
        f"--window-size={width},{height}",
        f"--screenshot={screenshot_path}" if screenshot_path is not None else "--dump-dom",
        page_url,
    )


def assert_png(path: Path, expected_width: int, expected_height: int) -> None:
    header = path.read_bytes()[:24]
    signature = b"\x89PNG\r\n\x1a\n"
    if len(header) < 24 or header[:8] != signature:
        raise RuntimeError("browser output is not a complete PNG")
    width, height = struct.unpack(">II", header[16:24])
    if (width, height) != (expected_width, expected_height):
        raise RuntimeError(
            f"browser output is {width}x{height}, expected {expected_width}x{expected_height}"
        )


async def _read_stderr(stream: asyncio.StreamReader | None) -> str:
    if stream is None:
        return ""
    chunks: list[bytes] = []
    size = 0
    while chunk := await stream.read(4096):
        if size < 16_000:
            kept = chunk[: 16_000 - size]
            chunks.append(kept)
            size += len(kept)
    return b"".join(chunks).decode("utf-8", "replace")


async def _stop_browser(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        await asyncio.wait_for(process.wait(), KILL_GRACE_SECONDS)
    except TimeoutError:
        process.kill()
        await process.wait()


async def read_dom(browser: Path, args: Sequence[str]) -> str:
    """Measure a local HTML document in the same isolated headless browser."""
    process = await asyncio.create_subprocess_exec(
        str(browser),
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    async def document() -> str:
        output = bytearray()
        while chunk := await process.stdout.read(65_536):
            output.extend(chunk)
            if b"</html>" in output[-len(chunk) - 10 :]:
                return output.decode("utf-8")
        raise RuntimeError("browser failed to measure the story layout")

    try:
        # Chrome may keep running after dumping the document, just as with screenshots.
        return await asyncio.wait_for(document(), SCREENSHOT_TIMEOUT_SECONDS)
    finally:
        await _stop_browser(process)


async def capture_screenshot(
    browser: Path,
    args: Sequence[str],
    screenshot_path: Path,
    *,
    timeout_seconds: float = SCREENSHOT_TIMEOUT_SECONDS,
) -> None:
    """Capture until Chrome's PNG stops growing, always terminating Chrome."""

    process = await asyncio.create_subprocess_exec(
        str(browser),
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    stderr_task = asyncio.create_task(_read_stderr(process.stderr))
    started_at = time.monotonic()
    previous_size = -1
    stable_checks = 0
    try:
        while time.monotonic() - started_at < timeout_seconds:
            try:
                size = screenshot_path.stat().st_size
            except FileNotFoundError:
                size = -1
            if size > 0 and size == previous_size:
                stable_checks += 1
            else:
                stable_checks = 0
            previous_size = size
            if stable_checks >= STABLE_CHECKS_REQUIRED:
                size_arg = next(value for value in args if value.startswith("--window-size="))
                width, height = (
                    int(value) for value in size_arg.removeprefix("--window-size=").split(",")
                )
                assert_png(screenshot_path, width, height)
                return
            if process.returncode is not None:
                if process.returncode == 0 and size > 0:
                    size_arg = next(value for value in args if value.startswith("--window-size="))
                    width, height = (
                        int(value) for value in size_arg.removeprefix("--window-size=").split(",")
                    )
                    assert_png(screenshot_path, width, height)
                    return
                stderr = await stderr_task
                raise RuntimeError(
                    f"browser exited with code {process.returncode}: {stderr.strip()}"
                )
            await asyncio.sleep(POLL_SECONDS)
        stderr = "" if not stderr_task.done() else stderr_task.result()
        raise RuntimeError(f"browser timed out while taking the screenshot: {stderr.strip()}")
    finally:
        await _stop_browser(process)
        if not stderr_task.done():
            with contextlib.suppress(asyncio.CancelledError):
                await stderr_task
