"""Atomic per-video artifact checkpoints; work_items remains the task authority."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


class VideoArtifacts:
    def __init__(self, runtime_root: Path, platform: str, video_id: str) -> None:
        digest = hashlib.sha256(f"{platform}:{video_id}".encode()).hexdigest()
        self.root = runtime_root / "videos" / digest
        self.root.mkdir(parents=True, exist_ok=True)

    def read(self, name: str) -> dict[str, Any] | None:
        path = self.root / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def save(self, name: str, data: dict[str, Any]) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=self.root, encoding="utf-8", delete=False
        ) as stream:
            json.dump(data, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        os.replace(temporary, self.root / name)
