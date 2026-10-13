from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "src/xhs_local"


def _names(path: Path) -> set[str]:
    return {item.name for item in path.iterdir() if item.name != "__pycache__"}


def test_top_level_package_matches_documented_module_boundaries() -> None:
    expected = {
        "configuration",
        "core",
        "observability",
        "pipeline",
        "plugins",
        "processing",
        "rendering",
        "storage",
    }
    actual = {
        path.name for path in PACKAGE_ROOT.iterdir() if path.is_dir() and path.name != "__pycache__"
    }

    assert actual == expected
    assert {path.name for path in (PROJECT_ROOT / "config").glob("*.yaml")} == {
        "app.yaml",
        "sources.yaml",
        "publishing.yaml",
    }


def test_documented_production_modules_match_the_physical_tree_exactly() -> None:
    assert _names(PACKAGE_ROOT) == {
        "__init__.py",
        "__main__.py",
        "app.py",
        "cli.py",
        "website.py",
        "configuration",
        "core",
        "observability",
        "pipeline",
        "plugins",
        "processing",
        "rendering",
        "storage",
    }
    expected_modules = {
        "core": {
            "__init__.py",
            "clock.py",
            "contracts.py",
            "errors.py",
            "identifiers.py",
            "states.py",
        },
        "configuration": {
            "__init__.py",
            "diff.py",
            "history.py",
            "loader.py",
            "manager.py",
            "models.py",
            "video_sources.py",
            "subscriptions.py",
        },
        "storage": {
            "__init__.py",
            "backups.py",
            "checkpoints.py",
            "database.py",
            "dead_letters.py",
            "migrations",
            "outbox.py",
            "records.py",
            "remote_operations.py",
            "retention.py",
            "schema.py",
            "work_items.py",
            "video_artifacts.py",
        },
        "pipeline": {
            "__init__.py",
            "collector.py",
            "dispatcher.py",
            "processor.py",
            "publisher.py",
            "recovery.py",
            "retention_worker.py",
            "retry_scheduler.py",
            "source_scheduler.py",
            "video.py",
            "agents.py",
        },
        "processing": {
            "__init__.py",
            "compliance.py",
            "provider.py",
            "router.py",
            "technology_news.py",
            "transcription.py",
            "video_summary.py",
        },
        "rendering": {"__init__.py", "chromium.py", "layout.py", "renderer.py", "templates"},
        "observability": {
            "__init__.py",
            "health.py",
            "logging.py",
            "metrics.py",
            "notifications.py",
            "status.py",
        },
    }
    for directory, expected in expected_modules.items():
        assert _names(PACKAGE_ROOT / directory) == expected
    assert _names(PACKAGE_ROOT / "storage/migrations") == {
        "001_initial.sql",
        "002_work_outbox.sql",
        "003_config_dlq_retention.sql",
        "004_news_favorites.sql",
        "005_news_deleted.sql",
    }
    assert _names(PACKAGE_ROOT / "rendering/templates") == {
        "news_text_editorial.html",
        "news_with_media.html",
        "x_post.html",
        "website.html",
    }


def test_repository_has_no_legacy_runtime_or_literal_placeholder_directories() -> None:
    assert not (PROJECT_ROOT / "backend").exists()
    assert not (PROJECT_ROOT / "test").exists()
    assert _names(PROJECT_ROOT / "tools") == {
        "migrate_legacy_data.py", "import_video_sources.py", "export_agents_targets.py",
        "restore_sensitive_data.py",
    }
    assert _names(PROJECT_ROOT / "ops") == {
        "com.xhs-local.power.plist",
        "com.xhs-local.pipeline.plist",
        "install_launchd.py",
        "run_cloud.sh",
        "install_cloud_service.sh",
        "xhs-publisher.service",
    }
    placeholders = [
        path
        for path in PACKAGE_ROOT.rglob("*")
        if path.is_dir() and path.name in {"<verified_source>", "<verified_sink>"}
    ]
    assert placeholders == []


def test_current_source_and_sink_plugins_are_self_describing() -> None:
    expected_source_files = {"manifest.yaml", "plugin.py", "client.py", "mapper.py", "README.md"}
    for plugin_id in ("telegram", "x"):
        directory = PACKAGE_ROOT / "plugins/sources" / plugin_id
        names = {path.name for path in directory.iterdir() if path.name != "__pycache__"}
        assert expected_source_files.issubset(names)
    for plugin_id in ("xiaohongshu",):
        directory = PACKAGE_ROOT / "plugins/sinks" / plugin_id
        assert (directory / "manifest.yaml").is_file()
        assert (directory / "plugin.py").is_file()
        assert (directory / "README.md").is_file()


def test_repository_contains_no_ambiguous_catch_all_modules() -> None:
    forbidden_names = {"utils.py", "common.py", "misc.py"}
    offenders = [path for path in PACKAGE_ROOT.rglob("*.py") if path.name in forbidden_names]
    forbidden_directories = [
        path
        for path in PACKAGE_ROOT.rglob("*")
        if path.is_dir() and path.name in {"utils", "common", "misc"}
    ]

    assert offenders == []
    assert forbidden_directories == []
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "/runtime/" in gitignore or "runtime/" in gitignore
