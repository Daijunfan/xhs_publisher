from __future__ import annotations

import asyncio
import time
from http.cookiejar import Cookie
from pathlib import Path

import pytest
from yt_dlp.cookies import YoutubeDLCookieJar

from xhs_local.plugins.sources.video.client import VideoClient
from xhs_local.plugins.sources.youtube.session import export_session


def cookie(domain, name):
    return Cookie(
        0,
        name,
        "private-test-value",
        None,
        False,
        domain,
        True,
        domain.startswith("."),
        "/",
        True,
        True,
        int(time.time()) + 3600,
        False,
        None,
        None,
        {},
    )


def test_only_youtube_cookies_are_exported_from_explicit_profile(tmp_path, monkeypatch, capsys):
    calls = []

    def extract(browser, profile, logger):
        calls.append((browser, profile))
        return [
            cookie(".youtube.com", "SID"),
            cookie("accounts.youtube.com", "SESSION"),
            cookie(".google.com", "SID"),
            cookie(".example.com", "SECRET"),
        ]

    monkeypatch.setattr(
        "xhs_local.plugins.sources.youtube.session.extract_cookies_from_browser", extract
    )
    path = tmp_path / "cookies.txt"
    export_session("Profile 1", path)
    jar = YoutubeDLCookieJar(str(path))
    jar.load()
    assert {entry.domain for entry in jar} == {".youtube.com", "accounts.youtube.com"}
    assert path.stat().st_mode & 0o777 == 0o600
    assert calls == [("chrome", "Profile 1")]
    captured = capsys.readouterr()
    assert "private-test-value" not in captured.out + captured.err


def test_parallel_cookie_copies_do_not_mutate_the_user_session(tmp_path):
    seed = tmp_path / "seed.txt"
    seed.write_text("private-session")
    client = VideoClient(cookie_file=str(seed))
    paths = []

    async def run():
        async with client.cookies() as first, client.cookies() as second:
            paths.extend([Path(first), Path(second)])
            assert first != second
            Path(first).write_text("updated-by-extractor")
            assert Path(second).read_text() == "private-session"
            assert Path(second).stat().st_mode & 0o777 == 0o600
        assert all(not path.exists() for path in paths)

    asyncio.run(run())
    assert seed.read_text() == "private-session"


@pytest.mark.parametrize("origin", ["metadata", "audio", "discover"])
def test_rate_limit_cools_all_shared_client_requests_without_rewriting_cookies(
    tmp_path, monkeypatch, origin
):
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from xhs_local.core.errors import TransientError
    from xhs_local.plugins.sources.video import client as video
    from xhs_local.plugins.sources.youtube import client as youtube

    now = [100.0]
    monkeypatch.setattr(video, "time", SimpleNamespace(monotonic=lambda: now[0]))
    seed = tmp_path / "cookies.txt"
    seed.write_text("private-original")
    client = youtube.YouTubeClient(cookie_file=seed)
    calls, copies = [], []

    async def command(arguments, **_kwargs):
        calls.append(arguments)
        cookie_path = (
            arguments[arguments.index("--cookies") + 1]
            if "--cookies" in arguments else arguments[-2]
        )
        copy = Path(cookie_path)
        copies.append(copy)
        assert copy != seed and copy.read_text() == "private-original"
        copy.write_text("extractor-cookie-update")
        if len(calls) == 1:
            raise TransientError("fixture limit", code="YOUTUBE_RATE_LIMITED")
        return b"{}"

    monkeypatch.setattr(video, "run_command", command)
    monkeypatch.setattr(youtube, "run_command", command)

    async def request(kind):
        if kind == "metadata":
            return await client.metadata("https://example.test/video")
        if kind == "audio":
            return await client.audio("https://example.test/video", tmp_path / "audio")
        return await client.discover("https://example.test/creator", datetime.now(UTC))

    async def run():
        with pytest.raises(TransientError) as error:
            await request(origin)
        assert error.value.code == "YOUTUBE_RATE_LIMITED"
        deadline = client.cooldown_until
        assert deadline == 3700
        now[0] += 30
        for kind in ("metadata", "audio", "discover"):
            with pytest.raises(TransientError) as blocked:
                await request(kind)
            assert blocked.value.code == "YOUTUBE_RATE_LIMITED"
        assert len(calls) == 1 and client.cooldown_until == deadline
        now[0] = deadline + 1
        assert await request("metadata") == {}

    asyncio.run(run())
    assert len(calls) == 2 and all(not copy.exists() for copy in copies)
    assert seed.read_text() == "private-original"


def test_shared_cooldown_is_checked_after_waiting_for_semaphore(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from xhs_local.core.errors import TransientError
    from xhs_local.plugins.sources.video import client as video

    monkeypatch.setattr(video, "time", SimpleNamespace(monotonic=lambda: 100))

    async def forbidden(*_args, **_kwargs):
        pytest.fail("a queued request must not run after another request establishes cooldown")

    monkeypatch.setattr(video, "run_command", forbidden)
    client = VideoClient(concurrency=1)

    async def run():
        await client.semaphore.acquire()
        task = asyncio.create_task(client.metadata("https://example.test/video"))
        await asyncio.sleep(0)
        client.cooldown_until = 3700
        client.semaphore.release()
        with pytest.raises(TransientError) as blocked:
            await task
        assert blocked.value.code == "YOUTUBE_RATE_LIMITED"
        assert client.cooldown_until == 3700

    asyncio.run(run())


def test_youtube_uses_official_pacing_for_cli_and_discovery(monkeypatch):
    from xhs_local.plugins.sources.youtube import client as youtube

    args = youtube.YouTubeClient().command()
    assert args[args.index("--sleep-requests") + 1] == "0.75"
    assert args[args.index("--sleep-interval") + 1] == "10"
    assert args[args.index("--max-sleep-interval") + 1] == "20"
    assert "--sleep-requests" not in VideoClient().command()
    options = []

    class Ydl:
        def __init__(self, configuration):
            options.append(configuration)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def extract_info(self, *_args, **_kwargs):
            return {"entries": []}

    monkeypatch.setattr(youtube, "YoutubeDL", Ydl)
    youtube.discover_uploads("https://example.test/creator", 0)
    assert options[0]["sleep_interval_requests"] == 0.75
    assert options[0]["sleep_interval"] == 10
    assert options[0]["max_sleep_interval"] == 20


def test_discovery_stops_resolving_peer_metadata_after_explicit_rate_limit():
    from xhs_local.plugins.sources.youtube.client import recent_uploads

    calls = []

    def limited(url):
        calls.append(url)
        raise RuntimeError("Your account has been rate-limited by YouTube for up to an hour")

    with pytest.raises(RuntimeError, match="rate-limited"):
        list(recent_uploads({"entries": [{"id": "one"}, {"id": "two"}]}, 0, limited))
    assert len(calls) == 1
