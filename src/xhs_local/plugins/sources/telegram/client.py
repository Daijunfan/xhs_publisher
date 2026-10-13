"""Telethon transport and interactive Session renewal boundary."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sqlite3
import subprocess
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from telethon import TelegramClient, utils
from telethon.tl.functions.channels import GetFullChannelRequest

from xhs_local.core.errors import AuthenticationRequired
from xhs_local.plugins.contracts import CancellationToken, PluginTarget

from .mapper import DownloadedMedia, image_mime_type, safe_media_name

AUTO_RECONNECT_ATTEMPTS = 3
DISCONNECT_TIMEOUT_SECONDS = 30.0
TRANSPORT_ERRORS = (
    TimeoutError,
    ConnectionError,
    OSError,
    EOFError,
    BufferError,
    sqlite3.OperationalError,
)
ClientFactory = Callable[[str, int, str], Any]


def _system_proxy() -> tuple[str, str, int, bool, str | None, str | None] | None:
    """Read the active macOS proxy without starting or modifying proxy software."""

    proxies = urllib.request.getproxies()
    for name, proxy_type in (("socks", "socks5"), ("https", "http"), ("http", "http")):
        value = proxies.get(name)
        if not value:
            continue
        parsed = urlparse(value if "://" in value else f"{proxy_type}://{value}")
        if not parsed.hostname or parsed.port is None:
            continue
        return (
            proxy_type,
            parsed.hostname,
            parsed.port,
            True,
            unquote(parsed.username) if parsed.username else None,
            unquote(parsed.password) if parsed.password else None,
        )
    return None


def _polling_client(session: str, api_id: int, api_hash: str) -> TelegramClient:
    """Build a pull-only client; the crawler does not consume Telegram updates."""

    return TelegramClient(
        session,
        api_id,
        api_hash,
        receive_updates=False,
        connection_retries=AUTO_RECONNECT_ATTEMPTS,
        retry_delay=1,
        auto_reconnect=True,
        proxy=_system_proxy(),
    )


def validate_api_credentials(api_id: Any, api_hash: Any) -> tuple[int, str]:
    if isinstance(api_id, bool):
        raise ValueError("Telegram api_id must be a positive integer")
    try:
        normalized_id = int(api_id)
    except (TypeError, ValueError) as error:
        raise ValueError("Telegram api_id must be a positive integer") from error
    normalized_hash = str(api_hash or "").strip()
    if (
        normalized_id < 1
        or len(normalized_hash) != 32
        or any(character not in "0123456789abcdefABCDEF" for character in normalized_hash)
    ):
        raise ValueError("Telegram api_id/api_hash are invalid")
    return normalized_id, normalized_hash


def session_file(session_root: str | Path) -> Path:
    root = Path(session_root).expanduser().resolve()
    return root if root.suffix == ".session" else Path(f"{root}.session")


def telethon_session_root(session_path: str | Path) -> Path:
    path = Path(session_path).expanduser().resolve()
    return path.with_suffix("") if path.suffix == ".session" else path


def activate_session(replacement: Path, current: Path, stamp: str) -> Path | None:
    """Atomically activate a verified Session and retain the old file."""

    replacement = replacement.expanduser().resolve()
    current = current.expanduser().resolve()
    if not replacement.is_file():
        raise FileNotFoundError(f"new Telegram session was not created: {replacement}")
    if replacement == current:
        raise ValueError("replacement and current Telegram sessions must differ")
    current.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if current.exists():
        backup = current.with_name(f"{current.stem}.revoked-{stamp}.session")
        if backup.exists():
            raise FileExistsError(f"refusing to overwrite session backup: {backup}")
        current.replace(backup)
        journal = current.with_name(f"{current.name}-journal")
        if journal.exists():
            journal.replace(backup.with_name(f"{backup.name}-journal"))
    try:
        replacement.replace(current)
    except BaseException:
        if backup is not None and not current.exists():
            backup.replace(current)
            backup_journal = backup.with_name(f"{backup.name}-journal")
            if backup_journal.exists():
                backup_journal.replace(current.with_name(f"{current.name}-journal"))
        raise
    os.chmod(current, 0o600)
    return backup


async def authorize_telegram_session(
    session_path: str | Path,
    *,
    api_id: int | None = None,
    api_hash: str | None = None,
    client_factory: ClientFactory = TelegramClient,
    output: Callable[[str], None] = print,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Path | None:
    """Interactively replace a Session; suitable for a thin CLI command."""

    normalized_id, normalized_hash = validate_api_credentials(
        api_id if api_id is not None else os.environ.get("USER_API_ID", ""),
        api_hash if api_hash is not None else os.environ.get("USER_API_HASH", ""),
    )
    root = telethon_session_root(session_path)
    root.parent.mkdir(parents=True, exist_ok=True)
    stamp = now().astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    renewal_root = root.with_name(f".{root.name}-renewal-{stamp}-{os.getpid()}")
    replacement = session_file(renewal_root)
    current = session_file(root)
    client = client_factory(str(renewal_root), normalized_id, normalized_hash)
    output("Telegram will prompt locally for login details.")
    try:
        try:
            await client.start()
            if not await client.is_user_authorized():
                raise RuntimeError("Telegram did not authorize the replacement session")
        finally:
            await client.disconnect()
    except BaseException:
        replacement.unlink(missing_ok=True)
        replacement.with_name(f"{replacement.name}-journal").unlink(missing_ok=True)
        raise
    backup = activate_session(replacement, current, stamp)
    output(f"Authorized session installed at {current}")
    if backup is not None:
        output(f"Revoked session retained at {backup}")
    return backup


class TelegramTransport:
    """One lazily connected Telethon client shared by bounded target calls."""

    def __init__(
        self,
        *,
        session_path: str | Path,
        api_id: int,
        api_hash: str,
        max_image_bytes: int,
        fetch_timeout_seconds: float,
        media_timeout_seconds: float,
        client_factory: ClientFactory = _polling_client,
        peer_id_factory: Callable[[Any], int] = utils.get_peer_id,
    ) -> None:
        self.session_root = telethon_session_root(session_path)
        self.api_id, self.api_hash = validate_api_credentials(api_id, api_hash)
        self.max_image_bytes = int(max_image_bytes)
        self.fetch_timeout_seconds = float(fetch_timeout_seconds)
        self.media_timeout_seconds = float(media_timeout_seconds)
        if self.max_image_bytes < 1:
            raise ValueError("max_image_bytes must be positive")
        if self.fetch_timeout_seconds <= 0 or self.media_timeout_seconds <= 0:
            raise ValueError("Telegram timeouts must be positive")
        self._client_factory = client_factory
        self._peer_id_factory = peer_id_factory
        self._client: Any | None = None
        self._connection_lock = asyncio.Lock()
        self._request_lock = asyncio.Lock()

    def _timeout(self, configured: float, deadline: float | None) -> float:
        if deadline is None:
            return configured
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Telegram collection deadline passed")
        return min(configured, remaining)

    @staticmethod
    def _disconnected(client: Any) -> bool:
        future = getattr(client, "disconnected", None)
        if future is None or not callable(getattr(future, "done", None)):
            return False
        if not future.done():
            return False
        with contextlib.suppress(asyncio.CancelledError, Exception):
            future.exception()
        return True

    @staticmethod
    async def _safe_disconnect(client: Any) -> None:
        try:
            async with asyncio.timeout(DISCONNECT_TIMEOUT_SECONDS):
                await client.disconnect()
        except (TimeoutError, Exception):
            return

    async def _connected_client(self, deadline: float | None = None) -> Any:
        client: Any | None = None
        try:
            async with asyncio.timeout(self._timeout(self.fetch_timeout_seconds, deadline)):
                async with self._connection_lock:
                    if self._client is None:
                        current_session = session_file(self.session_root)
                        if not current_session.is_file():
                            raise AuthenticationRequired(
                                f"Telegram session is missing: {current_session}"
                            )
                        self._client = self._client_factory(
                            str(self.session_root), self.api_id, self.api_hash
                        )
                    client = self._client
                    self._disconnected(client)
                    if not client.is_connected():
                        await client.connect()
                if not client.is_connected():
                    raise ConnectionError("Telegram client disconnected during setup")
                authorized = await client.is_user_authorized()
        except TRANSPORT_ERRORS:
            if client is not None:
                await self._discard_client(client)
            raise
        if not authorized:
            raise AuthenticationRequired("Telegram session is not authorized")
        return client

    async def _discard_client(self, client: Any) -> None:
        """Drop a broken shared transport so the next call creates a clean connection."""

        should_disconnect = False
        try:
            async with asyncio.timeout(DISCONNECT_TIMEOUT_SECONDS):
                async with self._connection_lock:
                    if self._client is client:
                        self._client = None
                        should_disconnect = True
        except TimeoutError:
            if self._client is client:
                self._client = None
                should_disconnect = True
        if should_disconnect:
            await self._safe_disconnect(client)

    async def healthcheck(self, target: PluginTarget, deadline: float | None) -> int:
        client = None
        try:
            async with asyncio.timeout(self._timeout(self.fetch_timeout_seconds, deadline)):
                async with self._request_lock:
                    client = await self._connected_client(deadline)
                    entity = await client.get_entity(target.locator)
        except TRANSPORT_ERRORS:
            if client is not None:
                await self._discard_client(client)
            raise
        return int(self._peer_id_factory(entity))

    async def fetch_messages(
        self,
        target: PluginTarget,
        *,
        min_message_id: int | None,
        limit: int,
        deadline: float | None,
        cancellation: CancellationToken,
    ) -> tuple[int, list[Any]]:
        cancellation.raise_if_cancelled()
        client = None
        try:
            async with asyncio.timeout(self._timeout(self.fetch_timeout_seconds, deadline)):
                async with self._request_lock:
                    client = await self._connected_client(deadline)
                    entity = await client.get_entity(target.locator)
                    channel_id = int(self._peer_id_factory(entity))
                    request: dict[str, Any] = {"limit": limit}
                    if min_message_id is not None:
                        request["min_id"] = min_message_id
                    messages: list[Any] = []
                    async for message in client.iter_messages(entity, **request):
                        cancellation.raise_if_cancelled()
                        messages.append(message)
        except TRANSPORT_ERRORS:
            if client is not None:
                await self._discard_client(client)
            raise
        return channel_id, messages

    async def channel_avatar(
        self,
        target: PluginTarget,
        *,
        known_photo_id: str | None,
        deadline: float | None,
        cancellation: CancellationToken,
    ) -> tuple[str | None, bytes | None]:
        """Read the configured channel's own photo, never a message/forward author."""
        cancellation.raise_if_cancelled()
        client = None
        try:
            async with asyncio.timeout(self._timeout(self.media_timeout_seconds, deadline)):
                async with self._request_lock:
                    client = await self._connected_client(deadline)
                    entity = await client.get_entity(target.locator)
                    photo_id = getattr(getattr(entity, "photo", None), "photo_id", None)
                    if photo_id is None:
                        return None, None
                    photo_id = str(photo_id)
                    if photo_id == known_photo_id:
                        return photo_id, None
                    data = await client.download_profile_photo(entity, file=bytes)
        except TRANSPORT_ERRORS:
            if client is not None:
                await self._discard_client(client)
            raise
        cancellation.raise_if_cancelled()
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise ValueError("Telegram channel profile photo is unavailable")
        data = bytes(data)
        if len(data) > self.max_image_bytes or not data.startswith(b"\xff\xd8\xff"):
            raise ValueError("Telegram channel profile photo is not a bounded JPEG")
        return photo_id, data

    async def download_image(
        self,
        message: Any,
        *,
        channel_id: int,
        deadline: float | None,
        cancellation: CancellationToken,
    ) -> DownloadedMedia | None:
        cancellation.raise_if_cancelled()
        mime_type = image_mime_type(message)
        if mime_type is None:
            return None
        file = getattr(message, "file", None)
        declared_size = getattr(file, "size", None) if file is not None else None
        if isinstance(declared_size, int) and declared_size > self.max_image_bytes:
            raise ValueError(f"image is {declared_size} bytes; limit is {self.max_image_bytes}")
        client = None
        try:
            async with asyncio.timeout(self._timeout(self.media_timeout_seconds, deadline)):
                async with self._request_lock:
                    client = await self._connected_client(deadline)
                    payload = await client.download_media(message, file=bytes)
        except TRANSPORT_ERRORS:
            if client is not None:
                await self._discard_client(client)
            raise
        cancellation.raise_if_cancelled()
        if not isinstance(payload, (bytes, bytearray)) or not payload:
            return None
        data = bytes(payload)
        if len(data) > self.max_image_bytes:
            raise ValueError(f"downloaded image exceeds {self.max_image_bytes} bytes")
        message_id = int(message.id)
        width = getattr(file, "width", None) if file is not None else None
        height = getattr(file, "height", None) if file is not None else None
        return DownloadedMedia(
            data=data,
            mime_type=mime_type,
            file_name=safe_media_name(
                getattr(file, "name", None) if file is not None else None,
                channel_id=channel_id,
                message_id=message_id,
                mime_type=mime_type,
            ),
            width=int(width) if isinstance(width, int) else None,
            height=int(height) if isinstance(height, int) else None,
        )

    async def channel_details(self, target: PluginTarget, *, deadline: float | None) -> dict:
        client = await self._connected_client(deadline)
        async with asyncio.timeout(self._timeout(self.fetch_timeout_seconds, deadline)):
            entity = await client.get_entity(target.locator)
            result = await client(GetFullChannelRequest(entity))
        count = getattr(result.full_chat, "participants_count", None)
        return {"subscriberCount": count} if isinstance(count, int) else {}

    async def document_preview(
        self,
        message: Any,
        *,
        channel_id: int,
        deadline: float | None,
        cancellation: CancellationToken,
        document: Path | None = None,
    ) -> DownloadedMedia | None:
        data = None
        if getattr(message.document, "thumbs", None):
            client = await self._connected_client(deadline)
            async with asyncio.timeout(self._timeout(self.media_timeout_seconds, deadline)):
                data = await client.download_media(message, file=bytes, thumb=-1)
        elif document is not None and str(message.file.mime_type) == "application/pdf":

            def cover():
                destination = document.with_suffix(".preview")
                try:
                    subprocess.run(
                        [
                            "pdftoppm",
                            "-f",
                            "1",
                            "-l",
                            "1",
                            "-singlefile",
                            "-scale-to",
                            "400",
                            "-jpeg",
                            str(document),
                            str(destination),
                        ],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=45,
                    )
                    return Path(str(destination) + ".jpg").read_bytes()
                finally:
                    Path(str(destination) + ".jpg").unlink(missing_ok=True)

            data = await asyncio.to_thread(cover)
        cancellation.raise_if_cancelled()
        if (
            not isinstance(data, bytes)
            or len(data) > self.max_image_bytes
            or not data.startswith(b"\xff\xd8\xff")
        ):
            return None
        return DownloadedMedia(
            data=data,
            mime_type="image/jpeg",
            file_name=f"telegram-{channel_id}-{message.id}-preview.jpg",
        )

    async def download_document(
        self,
        message: Any,
        *,
        channel_id: int,
        directory: Path,
        deadline: float | None,
        cancellation: CancellationToken,
    ) -> DownloadedMedia:
        """Stream original Telegram document bytes to disk; interrupted files resume."""
        file = message.file
        expected = int(file.size or 0)
        if expected < 1 or expected > 2 * 1024**3:
            raise ValueError("Telegram document must be between 1 byte and 2 GiB")
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{channel_id}-{message.document.id}.part"
        offset = destination.stat().st_size if destination.exists() else 0
        if offset > expected:
            destination.unlink()
            offset = 0
        client = await self._connected_client(deadline)
        async with asyncio.timeout(self._timeout(max(self.media_timeout_seconds, 900), deadline)):
            with destination.open("ab") as stream:
                async for chunk in client.iter_download(
                    message.document, offset=offset, request_size=512 * 1024
                ):
                    cancellation.raise_if_cancelled()
                    stream.write(chunk)
                    offset += len(chunk)
                    if offset > expected:
                        raise ValueError("Telegram document exceeds its declared size")
        if offset != expected:
            raise ValueError("Telegram document is incomplete")
        mime = str(file.mime_type or "application/octet-stream")
        return DownloadedMedia(
            data=destination,
            mime_type=mime,
            file_name=safe_media_name(
                file.name,
                channel_id=channel_id,
                message_id=int(message.id),
                mime_type=mime,
            ),
        )

    async def close(self) -> None:
        async with self._connection_lock:
            client, self._client = self._client, None
        if client is not None:
            await self._safe_disconnect(client)
