from __future__ import annotations

import asyncio
import struct
from pathlib import Path

import pytest

from xhs_local.rendering.chromium import assert_png, find_browser, read_dom, screenshot_args


def png_header(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", width, height)


def test_screenshot_arguments_keep_browser_offline_and_exact_size(tmp_path: Path) -> None:
    args = screenshot_args(
        width=1080,
        height=1440,
        profile_dir=tmp_path / "profile",
        screenshot_path=tmp_path / "card.png",
        page_url="file:///tmp/card.html",
    )
    assert "--headless=new" in args
    assert "--disable-background-networking" in args
    assert "--force-device-scale-factor=1" in args
    assert "--window-size=1080,1440" in args
    assert args[-1] == "file:///tmp/card.html"


def test_png_validation_checks_signature_and_dimensions(tmp_path: Path) -> None:
    path = tmp_path / "card.png"
    path.write_bytes(png_header(1080, 1440))
    assert_png(path, 1080, 1440)
    with pytest.raises(RuntimeError, match="expected 800x800"):
        assert_png(path, 800, 800)
    path.write_bytes(b"not a png")
    with pytest.raises(RuntimeError, match="complete PNG"):
        assert_png(path, 1080, 1440)


def test_explicit_browser_must_be_executable(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not executable"):
        find_browser(tmp_path / "missing")


def test_dom_measurement_stops_browser_after_document_without_waiting_for_exit(monkeypatch):
    stopped = []

    async def create(*args, **kwargs):
        class Process:
            returncode = None
            stdout = asyncio.StreamReader()

            def send_signal(self, _signal):
                stopped.append(True)

            async def wait(self):
                self.returncode = 0
                return 0

        process = Process()
        process.stdout.feed_data(b"<html>" + b"a" * 80_000 + b"</html>")
        # No EOF: real Chrome can remain alive after producing its result.
        return process

    monkeypatch.setattr("xhs_local.rendering.chromium.asyncio.create_subprocess_exec", create)
    document = asyncio.run(read_dom(Path("/browser"), ("--dump-dom",)))
    assert document.endswith("</html>")
    assert len(document) > 80_000
    assert stopped == [True]
