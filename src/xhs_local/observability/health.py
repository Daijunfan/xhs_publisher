"""Minimal localhost-only HTTP live/ready/status endpoint."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any


class HealthServer:
    def __init__(
        self,
        host: str,
        port: int,
        snapshot: Callable[[], dict[str, Any]],
    ) -> None:
        if host != "127.0.0.1":
            raise ValueError("health server must bind to 127.0.0.1")
        self.host = host
        self.port = port
        self.snapshot = snapshot
        self.server: asyncio.Server | None = None

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, self.host, self.port)

    async def close(self) -> None:
        if self.server is None:
            return
        self.server.close()
        await self.server.wait_closed()
        self.server = None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=2)
            path = line.decode(errors="replace").split(" ", 2)[1] if b" " in line else "/"
            state = self.snapshot()
            if path == "/health/live":
                body, status = {"live": True}, 200
            elif path == "/health/ready":
                ready = bool(state.get("ready"))
                body, status = {"ready": ready}, 200 if ready else 503
            else:
                body, status = state, 200
            encoded = json.dumps(body, ensure_ascii=False).encode()
            reason = "OK" if status == 200 else "Service Unavailable"
            writer.write(
                f"HTTP/1.1 {status} {reason}\r\nContent-Type: application/json; charset=utf-8\r\n"
                f"Content-Length: {len(encoded)}\r\nConnection: close\r\n\r\n".encode()
                + encoded
            )
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()
