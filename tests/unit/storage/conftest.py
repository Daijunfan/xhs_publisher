from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from xhs_local.storage.database import Database
from xhs_local.storage.schema import migrate


@pytest.fixture
def runtime_root(tmp_path: Path) -> Path:
    root = tmp_path / "runtime"
    root.mkdir()
    return root


@pytest.fixture
def database(runtime_root: Path) -> Iterator[Database]:
    opened = Database(runtime_root / "app.sqlite3")
    migrate(opened)
    try:
        yield opened
    finally:
        opened.close()
