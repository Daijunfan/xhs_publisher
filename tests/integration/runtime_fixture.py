"""Temporary application configuration with synthetic credential references."""

import shutil
from pathlib import Path

import yaml

from xhs_local.storage.database import Database
from xhs_local.storage.schema import migrate

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def prepare_runtime(tmp_path: Path, *, publication: bool = False) -> tuple[Path, Path]:
    config, runtime = tmp_path / "config", tmp_path / "runtime"
    shutil.copytree(PROJECT_ROOT / "config", config)
    (runtime / "sessions").mkdir(parents=True)
    (runtime / "secrets").mkdir()
    (runtime / "sessions/telegram-test.session").write_bytes(b"offline-session-fixture")
    (runtime / "secrets/youtube-test-cookies.txt").write_text("# Netscape HTTP Cookie File\n")
    (runtime / "secrets/deepseek-api-key").write_text("test-key")
    sources_path = config / "sources.yaml"
    sources = yaml.safe_load(sources_path.read_text())
    for source in sources["sources"]:
        if source["plugin"] == "telegram":
            source["options"].update(
                api_id=12345,
                api_hash="offline-fixture-hash",
                session_path="../runtime/sessions/telegram-test.session",
            )
        elif source["plugin"] == "youtube":
            source["options"]["cookie_file"] = "../runtime/secrets/youtube-test-cookies.txt"
    sources_path.write_text(yaml.safe_dump(sources, allow_unicode=True, sort_keys=False))
    if publication:
        publishing_path = config / "publishing.yaml"
        publishing = yaml.safe_load(publishing_path.read_text())
        for route in publishing["routes"]:
            if route["content_type"] == "tech_news":
                route["enabled"] = True
        publishing_path.write_text(
            yaml.safe_dump(publishing, allow_unicode=True, sort_keys=False)
        )
    with Database(runtime / "app.sqlite3") as database:
        migrate(database)
    return config, runtime
