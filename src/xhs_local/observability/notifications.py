"""Best-effort macOS notification for operator-actionable failures."""

from __future__ import annotations

import asyncio
import json
import subprocess


async def notify(title: str, message: str) -> None:
    script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"

    def invoke() -> None:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            check=False,
            timeout=10,
        )

    await asyncio.to_thread(invoke)
