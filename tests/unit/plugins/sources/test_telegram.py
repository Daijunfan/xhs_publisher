from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from xhs_local.plugins.contracts import (
    CancellationToken,
    CollectRequest,
    PluginContractError,
    PluginTarget,
    SourcePluginContext,
)
from xhs_local.plugins.sources.telegram.client import (
    TelegramTransport,
    _polling_client,
    _system_proxy,
    activate_session,
    authorize_telegram_session,
)
from xhs_local.plugins.sources.telegram.plugin import TelegramSourcePlugin

PROJECT_ROOT = Path(__file__).resolve().parents[4]
FIXTURE = PROJECT_ROOT / "tests/plugins/sources/telegram/messages.json"


def _messages() -> list[SimpleNamespace]:
    result = []
    for item in json.loads(FIXTURE.read_text(encoding="utf-8")):
        mime_type = item["mime_type"]
        file = (
            SimpleNamespace(
                mime_type=mime_type,
                name=item["file_name"],
                width=640,
                height=480,
                size=1024,
            )
            if mime_type
            else None
        )
        result.append(
            SimpleNamespace(
                id=item["id"],
                message=item["text"],
                date=datetime.fromisoformat(item["date"]),
                grouped_id=item["grouped_id"],
                photo=object() if mime_type == "image/png" else None,
                file=file,
            )
        )
    return result


class FakeTelegramClient:
    def __init__(self, messages, *, failing_download_id: int | None = None) -> None:
        self.messages = messages
        self.failing_download_id = failing_download_id
        self.connected = False
        self.authorized = True
        self.min_ids: list[int | None] = []
        self.disconnects = 0

    def is_connected(self) -> bool:
        return self.connected

    async def connect(self) -> None:
        self.connected = True

    async def is_user_authorized(self) -> bool:
        return self.authorized

    async def get_entity(self, locator: str):
        if locator == "broken_channel":
            raise RuntimeError("channel unavailable")
        return SimpleNamespace(id=42)

    async def iter_messages(self, _entity, *, limit: int, min_id: int | None = None):
        self.min_ids.append(min_id)
        eligible = [message for message in self.messages if min_id is None or message.id > min_id]
        for message in list(reversed(eligible))[:limit]:
            yield message

    async def download_media(self, message, *, file):
        assert file is bytes
        if message.id == self.failing_download_id:
            raise RuntimeError("download failed")
        return b"GIF89a-original" if message.file.mime_type == "image/gif" else b"\x89PNG\r\n\x1a\n"

    async def disconnect(self) -> None:
        self.disconnects += 1
        self.connected = False


def _plugin(tmp_path: Path, client: FakeTelegramClient, logs=None) -> TelegramSourcePlugin:
    (tmp_path / "telegram-user.session").write_bytes(b"authorized fixture")
    context = SourcePluginContext(
        source_id="telegram-main",
        runtime_root=tmp_path,
        options={
            "session_path": str(tmp_path / "telegram-user"),
            "lookback_hours": 24,
            "default_post_limit": 100,
            "max_image_bytes": 20 * 1024 * 1024,
            "api_id": 2040,
            "api_hash": "11111111111111111111111111111111",
            "fetch_timeout_seconds": 90,
            "media_timeout_seconds": 90,
        },
        log=(lambda event, fields: logs.append((event, fields)))
        if logs is not None
        else lambda *_: None,
    )
    return TelegramSourcePlugin(
        context,
        client_factory=lambda *_args: client,
        peer_id_factory=lambda entity: -1000000000000 - entity.id,
        environment={},
    )


def _request(target: PluginTarget, checkpoint=None) -> CollectRequest:
    return CollectRequest(
        source_id="telegram-main",
        target=target,
        checkpoint=checkpoint or {},
        observed_at=datetime(2026, 8, 19, 5, 0, tzinfo=UTC),
    )


def test_collect_preserves_album_media_gif_and_incremental_checkpoint(tmp_path: Path) -> None:
    client = FakeTelegramClient(_messages())
    plugin = _plugin(tmp_path, client)
    target = PluginTarget("telegram-test", "thehackernews", "The Hacker News")

    first = asyncio.run(plugin.collect(_request(target)))
    second = asyncio.run(plugin.collect(_request(target, first.checkpoint)))
    asyncio.run(plugin.close())

    assert [record.external_id for record in first.records] == ["101", "102", "103"]
    assert [record.group_id for record in first.records[:2]] == ["9001", "9001"]
    assert first.records[0].attachments[0].mime_type == "image/png"
    assert first.records[1].attachments[0].mime_type == "image/gif"
    assert first.records[1].attachments[0].data == b"GIF89a-original"
    assert first.records[2].attachments == ()
    assert first.checkpoint == {
        "locator": "thehackernews",
        "channel_id": -1000000000042,
        "max_message_id": 103,
        "channel_avatar": {"photo_id": None, "checked_at": "2026-08-19T05:00:00+00:00"},
    }
    assert second.records == ()
    assert client.min_ids == [None, 103]
    assert client.disconnects == 1


def test_first_collection_discards_older_history_but_advances_checkpoint(tmp_path: Path) -> None:
    messages = _messages()
    messages.append(
        SimpleNamespace(
            id=104,
            message="Old history must not be crawled after restart.",
            date=datetime(2026, 8, 17, 4, 0, tzinfo=UTC),
            grouped_id=None,
            photo=None,
            file=None,
        )
    )
    client = FakeTelegramClient(messages)
    plugin = _plugin(tmp_path, client)
    target = PluginTarget("telegram-test", "thehackernews", "The Hacker News")

    batch = asyncio.run(plugin.collect(_request(target)))

    assert [record.external_id for record in batch.records] == ["101", "102", "103"]
    assert batch.checkpoint["max_message_id"] == 104


def test_media_failure_is_isolated_and_text_record_survives(tmp_path: Path) -> None:
    logs = []
    client = FakeTelegramClient(_messages(), failing_download_id=101)
    plugin = _plugin(tmp_path, client, logs)
    target = PluginTarget("telegram-test", "thehackernews", "The Hacker News")

    batch = asyncio.run(plugin.collect(_request(target)))

    failed_record = next(record for record in batch.records if record.external_id == "101")
    assert failed_record.attachments == ()
    assert batch.errors == 1
    assert logs[0][0] == "telegram_media_error"


def test_target_failure_does_not_poison_shared_transport(tmp_path: Path) -> None:
    client = FakeTelegramClient(_messages())
    plugin = _plugin(tmp_path, client)
    broken = PluginTarget("broken", "broken_channel", "Broken")
    healthy = PluginTarget("healthy", "solidot", "Solidot")

    with pytest.raises(RuntimeError, match="unavailable"):
        asyncio.run(plugin.collect(_request(broken)))
    batch = asyncio.run(plugin.collect(_request(healthy)))

    assert len(batch.records) == 3


def test_transport_failure_discards_client_and_reconnects(tmp_path: Path) -> None:
    clients: list[FakeTelegramClient] = []

    class FailingClient(FakeTelegramClient):
        async def get_entity(self, _locator: str):
            raise TimeoutError("connection stalled")

    def factory(*_args):
        client = FailingClient([]) if not clients else FakeTelegramClient(_messages())
        clients.append(client)
        return client

    (tmp_path / "telegram-user.session").write_bytes(b"authorized fixture")
    transport = TelegramTransport(
        session_path=tmp_path / "telegram-user",
        api_id=2040,
        api_hash="11111111111111111111111111111111",
        max_image_bytes=1024,
        fetch_timeout_seconds=5,
        media_timeout_seconds=5,
        client_factory=factory,
        peer_id_factory=lambda entity: entity.id,
    )
    target = PluginTarget("telegram-test", "solidot", "Solidot")

    with pytest.raises(TimeoutError, match="stalled"):
        asyncio.run(transport.healthcheck(target, None))
    assert asyncio.run(transport.healthcheck(target, None)) == 42
    assert len(clients) == 2
    assert clients[0].disconnects == 1


def test_incomplete_read_discards_corrupted_client_and_reconnects(tmp_path: Path) -> None:
    clients: list[FakeTelegramClient] = []

    class TruncatedResponse(FakeTelegramClient):
        async def get_entity(self, _locator: str):
            raise asyncio.IncompleteReadError(partial=b"", expected=8)

    def factory(*_args):
        client = TruncatedResponse([]) if not clients else FakeTelegramClient(_messages())
        clients.append(client)
        return client

    (tmp_path / "telegram-user.session").write_bytes(b"authorized fixture")
    transport = TelegramTransport(
        session_path=tmp_path / "telegram-user",
        api_id=2040,
        api_hash="11111111111111111111111111111111",
        max_image_bytes=1024,
        fetch_timeout_seconds=5,
        media_timeout_seconds=5,
        client_factory=factory,
        peer_id_factory=lambda entity: entity.id,
    )
    target = PluginTarget("telegram-test", "solidot", "Solidot")

    with pytest.raises(asyncio.IncompleteReadError):
        asyncio.run(transport.healthcheck(target, None))
    assert asyncio.run(transport.healthcheck(target, None)) == 42
    assert len(clients) == 2
    assert clients[0].disconnects == 1


def test_connection_failure_discards_client_before_next_target(tmp_path: Path) -> None:
    clients: list[FakeTelegramClient] = []

    class ConnectFailure(FakeTelegramClient):
        async def connect(self) -> None:
            raise ConnectionError("network unavailable")

    def factory(*_args):
        client = ConnectFailure([]) if not clients else FakeTelegramClient(_messages())
        clients.append(client)
        return client

    (tmp_path / "telegram-user.session").write_bytes(b"authorized fixture")
    transport = TelegramTransport(
        session_path=tmp_path / "telegram-user",
        api_id=2040,
        api_hash="11111111111111111111111111111111",
        max_image_bytes=1024,
        fetch_timeout_seconds=5,
        media_timeout_seconds=5,
        client_factory=factory,
        peer_id_factory=lambda entity: entity.id,
    )
    target = PluginTarget("telegram-test", "solidot", "Solidot")

    with pytest.raises(ConnectionError, match="network unavailable"):
        asyncio.run(transport.healthcheck(target, None))
    assert asyncio.run(transport.healthcheck(target, None)) == 42
    assert len(clients) == 2
    assert clients[0].disconnects == 1


def test_completed_disconnected_future_reconnects_same_client(tmp_path: Path) -> None:
    (tmp_path / "telegram-user.session").write_bytes(b"authorized fixture")

    async def scenario() -> None:
        stale = FakeTelegramClient(_messages())
        stale.connected = False
        stale.disconnected = asyncio.get_running_loop().create_future()
        stale.disconnected.set_exception(asyncio.IncompleteReadError(partial=b"", expected=8))
        created = []

        def factory(*_args):
            created.append(object())
            return FakeTelegramClient(_messages())

        transport = TelegramTransport(
            session_path=tmp_path / "telegram-user",
            api_id=2040,
            api_hash="11111111111111111111111111111111",
            max_image_bytes=1024,
            fetch_timeout_seconds=5,
            media_timeout_seconds=5,
            client_factory=factory,
            peer_id_factory=lambda entity: entity.id,
        )
        transport._client = stale  # noqa: SLF001
        target = PluginTarget("telegram-test", "solidot", "Solidot")

        assert await transport.healthcheck(target, None) == 42
        assert created == []
        assert stale.connected is True
        assert stale.disconnects == 0

    asyncio.run(scenario())


def test_connection_lock_wait_is_bounded_by_collection_deadline(tmp_path: Path) -> None:
    (tmp_path / "telegram-user.session").write_bytes(b"authorized fixture")

    async def scenario() -> None:
        client = FakeTelegramClient(_messages())
        transport = TelegramTransport(
            session_path=tmp_path / "telegram-user",
            api_id=2040,
            api_hash="11111111111111111111111111111111",
            max_image_bytes=1024,
            fetch_timeout_seconds=5,
            media_timeout_seconds=5,
            client_factory=lambda *_args: client,
            peer_id_factory=lambda entity: entity.id,
        )
        await transport._connection_lock.acquire()  # noqa: SLF001
        try:
            target = PluginTarget("telegram-test", "solidot", "Solidot")
            with pytest.raises(TimeoutError):
                await transport.healthcheck(target, time.monotonic() + 0.01)
        finally:
            transport._connection_lock.release()  # noqa: SLF001

    asyncio.run(scenario())


def test_shared_client_serializes_target_requests(tmp_path: Path) -> None:
    (tmp_path / "telegram-user.session").write_bytes(b"authorized fixture")

    async def scenario() -> None:
        class BlockingClient(FakeTelegramClient):
            def __init__(self) -> None:
                super().__init__(_messages())
                self.entered = asyncio.Event()
                self.release = asyncio.Event()
                self.active = 0
                self.maximum_active = 0

            async def get_entity(self, _locator: str):
                self.active += 1
                self.maximum_active = max(self.maximum_active, self.active)
                self.entered.set()
                await self.release.wait()
                self.active -= 1
                return SimpleNamespace(id=42)

        client = BlockingClient()
        transport = TelegramTransport(
            session_path=tmp_path / "telegram-user",
            api_id=2040,
            api_hash="11111111111111111111111111111111",
            max_image_bytes=1024,
            fetch_timeout_seconds=5,
            media_timeout_seconds=5,
            client_factory=lambda *_args: client,
            peer_id_factory=lambda entity: entity.id,
        )
        first = asyncio.create_task(transport.healthcheck(PluginTarget("one", "one", "One"), None))
        await client.entered.wait()
        second = asyncio.create_task(transport.healthcheck(PluginTarget("two", "two", "Two"), None))
        await asyncio.sleep(0)
        assert client.maximum_active == 1
        client.release.set()

        assert await asyncio.gather(first, second) == [42, 42]
        assert client.maximum_active == 1

    asyncio.run(scenario())


def test_default_telegram_client_honors_current_macos_proxy(monkeypatch) -> None:
    captured = {}

    def factory(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr("xhs_local.plugins.sources.telegram.client.TelegramClient", factory)
    monkeypatch.setattr(
        "xhs_local.plugins.sources.telegram.client.urllib.request.getproxies",
        lambda: {"socks": "http://127.0.0.1:7897"},
    )
    client = _polling_client("session", 1, "hash")

    assert client is not None
    assert captured["args"] == ("session", 1, "hash")
    assert captured["kwargs"] == {
        "receive_updates": False,
        "connection_retries": 3,
        "retry_delay": 1,
        "auto_reconnect": True,
        "proxy": ("socks5", "127.0.0.1", 7897, True, None, None),
    }


def test_system_proxy_follows_changes_and_falls_back_to_direct(monkeypatch) -> None:
    values = iter(
        [
            {"https": "http://proxy-one.local:8080"},
            {"socks": "socks5://user:secret@proxy-two.local:1080"},
            {},
        ]
    )
    monkeypatch.setattr(
        "xhs_local.plugins.sources.telegram.client.urllib.request.getproxies",
        lambda: next(values),
    )

    assert _system_proxy() == ("http", "proxy-one.local", 8080, True, None, None)
    assert _system_proxy() == ("socks5", "proxy-two.local", 1080, True, "user", "secret")
    assert _system_proxy() is None


def test_cancellation_and_checkpoint_identity_are_enforced(tmp_path: Path) -> None:
    client = FakeTelegramClient(_messages())
    plugin = _plugin(tmp_path, client)
    target = PluginTarget("telegram-test", "solidot", "Solidot")
    cancellation = CancellationToken()
    cancellation.cancel()
    cancelled = CollectRequest(
        source_id="telegram-main",
        target=target,
        checkpoint={},
        observed_at=datetime.now(UTC),
        cancellation=cancellation,
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(plugin.collect(cancelled))
    with pytest.raises(PluginContractError, match="another locator"):
        asyncio.run(plugin.collect(_request(target, {"locator": "other", "max_message_id": 1})))


def test_session_activation_and_cli_callable_authorization_preserve_old_session(
    tmp_path: Path,
) -> None:
    current = tmp_path / "telegram-user.session"
    replacement = tmp_path / "replacement.session"
    current.write_bytes(b"old")
    replacement.write_bytes(b"new")

    backup = activate_session(replacement, current, "stamp")

    assert current.read_bytes() == b"new"
    assert backup is not None and backup.read_bytes() == b"old"
    assert not replacement.exists()

    class AuthorizingClient:
        def __init__(self, root: str, *_args) -> None:
            self.root = Path(root)

        async def start(self) -> None:
            Path(f"{self.root}.session").write_bytes(b"renewed")

        async def is_user_authorized(self) -> bool:
            return True

        async def disconnect(self) -> None:
            return None

    messages = []
    asyncio.run(
        authorize_telegram_session(
            current,
            api_id=12345,
            api_hash="11111111111111111111111111111111",
            client_factory=AuthorizingClient,
            output=messages.append,
            now=lambda: datetime(2026, 8, 19, tzinfo=UTC),
        )
    )
    assert current.read_bytes() == b"renewed"
    assert any("Authorized session installed" in message for message in messages)


class ProfileTelegramClient(FakeTelegramClient):
    def __init__(self, messages):
        super().__init__(messages)
        self.channel = SimpleNamespace(id=42, photo=SimpleNamespace(photo_id=700))
        self.profile_bytes = b"\xff\xd8\xff\xdbchannel-own-photo"
        self.profile_reads = []
        self.profile_error = False

    async def get_entity(self, locator):
        assert locator == "thehackernews"
        return self.channel

    async def download_profile_photo(self, entity, *, file):
        assert entity is self.channel
        assert file is bytes
        self.profile_reads.append(entity.id)
        if self.profile_error:
            raise RuntimeError("profile temporarily unavailable")
        return self.profile_bytes


def test_channel_own_avatar_checkpoint_without_news_and_changed_photo(tmp_path):
    client = ProfileTelegramClient([])
    plugin = _plugin(tmp_path, client)
    target = PluginTarget("telegram-test", "thehackernews", "The Hacker News")
    first = asyncio.run(plugin.collect(_request(target)))
    assert first.records == ()
    avatar = first.checkpoint["channel_avatar"]
    assert base64.b64decode(avatar["data"]) == client.profile_bytes
    assert avatar["sha256"] == hashlib.sha256(client.profile_bytes).hexdigest()
    second = asyncio.run(plugin.collect(_request(target, first.checkpoint)))
    assert second.checkpoint["channel_avatar"] == avatar
    assert client.profile_reads == [42]
    client.channel.photo.photo_id = 701
    client.profile_bytes += b"-changed"
    changed = asyncio.run(plugin.collect(_request(target, second.checkpoint)))
    assert changed.checkpoint["channel_avatar"]["photo_id"] == "701"
    assert base64.b64decode(changed.checkpoint["channel_avatar"]["data"]) == client.profile_bytes
    assert client.profile_reads == [42, 42]
    client.channel.photo = None
    absent = asyncio.run(plugin.collect(_request(target, changed.checkpoint)))
    assert absent.checkpoint["channel_avatar"]["photo_id"] is None
    assert "data" not in absent.checkpoint["channel_avatar"]
    asyncio.run(plugin.close())


def test_avatar_uses_configured_channel_not_forward_author_and_failure_keeps_news(tmp_path):
    messages = _messages()
    messages[0].sender = SimpleNamespace(id=999, photo=SimpleNamespace(photo_id=999))
    messages[0].fwd_from = SimpleNamespace(from_id=999)
    client = ProfileTelegramClient(messages)
    logs = []
    plugin = _plugin(tmp_path, client, logs)
    target = PluginTarget("telegram-test", "thehackernews", "The Hacker News")
    first = asyncio.run(plugin.collect(_request(target)))
    assert client.profile_reads == [42]
    assert all("avatar_attachment_index" not in record.payload for record in first.records)
    client.channel.photo.photo_id = 702
    client.profile_error = True
    failed = asyncio.run(plugin.collect(_request(target, first.checkpoint)))
    assert failed.checkpoint["channel_avatar"] == first.checkpoint["channel_avatar"]
    assert failed.errors == 1
    assert logs[-1][0] == "telegram_avatar_error"
    # A fresh collection still keeps ordinary news when profile download fails.
    latest = asyncio.run(plugin.collect(_request(target)))
    assert [record.external_id for record in latest.records] == ["101", "102", "103"]
    asyncio.run(plugin.close())
