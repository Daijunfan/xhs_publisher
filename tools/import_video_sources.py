"""Usage: .venv/bin/python tools/import_video_sources.py [creator-document.md]."""

import sys
from pathlib import Path

from xhs_local.configuration.video_sources import import_creator_document

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    document = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "bilibili_and_youtube.md"
    counts = import_creator_document(document, root / "config")
    print(
        f"Imported {counts}; sources default to disabled; key saved under runtime/secrets (0600)."
    )
