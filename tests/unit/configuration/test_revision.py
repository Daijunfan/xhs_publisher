from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from xhs_local.configuration.loader import ConfigurationError, load_snapshot

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _copy_config(tmp_path: Path) -> Path:
    destination = tmp_path / "config"
    shutil.copytree(PROJECT_ROOT / "config", destination)
    return destination


def test_revision_is_canonical_across_yaml_format_and_key_order(tmp_path: Path) -> None:
    root = _copy_config(tmp_path)
    original = load_snapshot(root)
    path = root / "app.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    path.write_text(
        "# formatting must not alter a semantic revision\n"
        + yaml.safe_dump(dict(reversed(tuple(data.items()))), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    reformatted = load_snapshot(root)

    assert reformatted.revision == original.revision
    assert len(original.revision) == 64


def test_any_one_of_the_three_files_changes_the_complete_revision(tmp_path: Path) -> None:
    root = _copy_config(tmp_path)
    revisions = {load_snapshot(root).revision}
    changes = (
        ("app.yaml", ("queues", "ingest_maxsize"), 101),
        ("sources.yaml", ("sources", 0, "poll_seconds"), 31),
        ("publishing.yaml", ("news", "publish_interval_minutes"), 16),
    )
    for index, (name, path_parts, value) in enumerate(changes):
        isolated = tmp_path / f"config-{index}"
        shutil.copytree(PROJECT_ROOT / "config", isolated)
        path = isolated / name
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        cursor = data
        for part in path_parts[:-1]:
            cursor = cursor[part]
        cursor[path_parts[-1]] = value
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        revisions.add(load_snapshot(isolated).revision)

    assert len(revisions) == 4


def test_invalid_or_partial_file_rejects_the_whole_snapshot(tmp_path: Path) -> None:
    root = _copy_config(tmp_path)
    sources = root / "sources.yaml"
    sources.write_text("version: 1\nsources:\n  - plugin: telegram\n", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_snapshot(root)

    sources.unlink()
    with pytest.raises(ConfigurationError, match="cannot read YAML"):
        load_snapshot(root)


def test_review_models_are_runtime_configurable_and_must_differ(tmp_path: Path) -> None:
    root = _copy_config(tmp_path)
    path = root / "publishing.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["news"]["first_review_model"] = "deepseek-v4-flash"
    data["news"]["second_review_model"] = "deepseek-v4-pro"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    swapped = load_snapshot(root)
    assert swapped.publishing.news.first_review_model == "deepseek-v4-flash"
    assert swapped.publishing.news.second_review_model == "deepseek-v4-pro"

    data["news"]["second_review_model"] = "deepseek-v4-flash"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="review_model"):
        load_snapshot(root)


def test_legacy_model_field_names_remain_rollback_compatible(tmp_path: Path) -> None:
    root = _copy_config(tmp_path)
    path = root / "publishing.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["news"]["compliance_model"] = data["news"].pop("first_review_model")
    data["news"]["quality_model"] = data["news"].pop("second_review_model")
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    restored = load_snapshot(root)
    assert restored.publishing.news.first_review_model == "deepseek-v4-pro"
    assert restored.publishing.news.second_review_model == "deepseek-flash"




def test_capacity_schedule_cannot_exceed_xiaohongshu_image_limit(tmp_path: Path) -> None:
    root = _copy_config(tmp_path)
    snapshot = load_snapshot(root)
    assert snapshot.publishing.news.max_news_per_note == 18
    assert snapshot.publishing.news.publish_interval_minutes == 20
    assert snapshot.publishing.news.restart_resume_minutes == 20
    assert snapshot.publishing.news.startup_collection_timeout_seconds == 180
    assert snapshot.publishing.news.previous_day_keep_minutes == 20
    assert snapshot.publishing.news.night_publish_interval_minutes == 30
    assert snapshot.publishing.news.night_end_hour == 8
    assert snapshot.publishing.news.codex_fallback_enabled is False
    assert snapshot.publishing.retry.transient_base_delay_seconds == 60
    assert snapshot.publishing.filters["tech_news"].minimum_text_characters == 1
    assert snapshot.publishing.news.source_publish_modes == {
        "telegram": "scheduled_only",
        "x": "scheduled_only",
        "youtube": "scheduled_only",
    }
    assert snapshot.publishing.news.source_batch_sizes == {}
    assert snapshot.publishing.news.source_immediate_five_star == {
        "telegram": False,
        "x": False,
        "youtube": False,
    }

    path = root / "publishing.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["news"].setdefault("source_batch_sizes", {})["x"] = 19
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    with pytest.raises(ConfigurationError, match="batch size"):
        load_snapshot(root)
