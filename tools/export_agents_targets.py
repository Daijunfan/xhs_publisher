"""Export public subscription fields for Core bootstrap; never source options."""

import json
from pathlib import Path

import yaml

root = Path(__file__).resolve().parents[1]
sources = yaml.safe_load((root / "config/sources.yaml").read_text())["sources"]
print(
    json.dumps(
        {
            "targets": [
                {
                    "targetId": target["id"],
                    "plugin": source["plugin"],
                    "locator": target["locator"],
                    "name": target["name"],
                    "enabled": bool(source.get("enabled", True) and target.get("enabled", True)),
                    "pollSeconds": target.get("poll_seconds") or source["poll_seconds"],
                }
                for source in sources
                if source["plugin"] in {"telegram", "x", "youtube"}
                for target in source.get("targets", [])
            ]
        },
        ensure_ascii=False,
    )
)
