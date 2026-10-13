from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from xhs_local.configuration.loader import load_snapshot
from xhs_local.plugins.contracts import PluginContractError, SourcePlugin
from xhs_local.plugins.registry import (
    SinkPluginRegistry,
    SourcePluginRegistry,
    load_manifest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_registry_discovers_sources_and_preserves_configured_targets() -> None:
    snapshot = load_snapshot(PROJECT_ROOT / "config")
    registry = SourcePluginRegistry()

    assert set(registry.discover()) == {"telegram", "x", "youtube"}
    telegram_config = next(
        source for source in snapshot.sources.sources if source.plugin == "telegram"
    )
    prepared = registry.prepare(
        telegram_config,
        config_root=PROJECT_ROOT / "config",
        runtime_root=snapshot.runtime_root,
    )

    assert [target.locator for target in prepared.targets] == [
        "GodlyNews1",
        "xhqcankao",
        "DNSPODT",
        "solidot",
        "zaihuapd",
        "tnews365",
        "thehackernews",
        "AI_DeepLearning",
        "DeepLearning_ai",
        "Artificial_intelligence_in",
        "computer_science_and_programming",
        "linuxgram",
        "machine_learning_courses",
        "trunkietrunk",
    ]
    plugin = registry.create(prepared, client_factory=lambda *_args: object())
    assert isinstance(plugin, SourcePlugin)

    x_config = next(source for source in snapshot.sources.sources if source.plugin == "x")
    prepared_x = registry.prepare(
        x_config,
        config_root=PROJECT_ROOT / "config",
        runtime_root=snapshot.runtime_root,
    )
    expected_x_locators = [target.locator for target in x_config.targets if target.enabled]
    actual_x_locators = [target.locator for target in prepared_x.targets]
    assert actual_x_locators == expected_x_locators
    assert len(actual_x_locators) == 295
    assert len(actual_x_locators) == len(set(locator.casefold() for locator in actual_x_locators))
    assert {"EmperoAI", "hackernews", "huggingface", "_jasonwei"}.issubset(actual_x_locators)
    assert {"jasonwei20", "matklad", "Locuza_"}.isdisjoint(actual_x_locators)
    assert all(f"@{target.locator}" in target.name for target in prepared_x.targets)
    assert isinstance(registry.create(prepared_x), SourcePlugin)


def test_offline_preflight_validates_manifest_import_contract_and_targets() -> None:
    snapshot = load_snapshot(PROJECT_ROOT / "config")
    registry = SourcePluginRegistry()
    source = next(item for item in snapshot.sources.sources if item.plugin == "telegram")
    prepared = registry.prepare(
        source,
        config_root=PROJECT_ROOT / "config",
        runtime_root=snapshot.runtime_root,
    )

    report = asyncio.run(registry.preflight(prepared))

    assert report.ok is True
    assert report.checks == ("manifest", "import", "contract", "options", "targets")


def test_manifest_rejects_unknown_fields_before_import(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "example"
    plugin_dir.mkdir()
    manifest = plugin_dir / "manifest.yaml"
    manifest.write_text(
        """id: example
kind: source
api_version: 1
version: 1
entrypoint: xhs_local.plugins.sources.example.plugin:Example
content_types: [tech_news]
source_options: {required: [], properties: {}, additional_properties: false}
target_options: {required: [], properties: {}, additional_properties: false}
unexpected: true
""",
        encoding="utf-8",
    )

    with pytest.raises(PluginContractError, match="unknown unexpected"):
        load_manifest(manifest)


def test_registry_rejects_unknown_plugin_without_platform_switch() -> None:
    registry = SourcePluginRegistry()
    with pytest.raises(PluginContractError, match="not installed"):
        registry.manifest("future_job_board")


def test_sink_registry_discovers_and_checks_current_adapters_without_platform_switch() -> None:
    registry = SinkPluginRegistry()

    assert set(registry.discover()) == {"xiaohongshu"}
    xhs = asyncio.run(registry.preflight(registry.prepare("xiaohongshu")))

    assert xhs.checks == ("manifest", "import", "contract", "capabilities")


def test_removed_file_sharing_plugins_cannot_be_reactivated():
    with pytest.raises(PluginContractError, match="not installed"):
        SourcePluginRegistry().manifest("local_documents")
    with pytest.raises(PluginContractError, match="not installed"):
        SinkPluginRegistry().prepare("baidu")
