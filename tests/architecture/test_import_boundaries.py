from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "src/xhs_local"


def _absolute_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _assert_no_prefix(directory: str, prefixes: tuple[str, ...]) -> None:
    violations = []
    for path in (PACKAGE_ROOT / directory).rglob("*.py"):
        for imported in _absolute_imports(path):
            if imported.startswith(prefixes):
                violations.append((path.relative_to(PROJECT_ROOT).as_posix(), imported))
    assert violations == []


def test_core_is_pure_and_storage_never_imports_runtime_components() -> None:
    _assert_no_prefix(
        "core",
        (
            "xhs_local.configuration",
            "xhs_local.observability",
            "xhs_local.pipeline",
            "xhs_local.plugins",
            "xhs_local.processing",
            "xhs_local.rendering",
            "xhs_local.storage",
        ),
    )
    _assert_no_prefix(
        "storage",
        (
            "xhs_local.configuration",
            "xhs_local.observability",
            "xhs_local.pipeline",
            "xhs_local.plugins",
            "xhs_local.processing",
            "xhs_local.rendering",
        ),
    )


def test_processing_and_rendering_do_not_import_platform_or_storage_details() -> None:
    forbidden = (
        "xhs_local.pipeline",
        "xhs_local.plugins",
        "xhs_local.storage",
    )
    _assert_no_prefix("processing", forbidden)
    _assert_no_prefix("rendering", forbidden)


def test_concrete_platform_adapters_are_wired_only_at_composition_boundaries() -> None:
    allowed = {
        "src/xhs_local/app.py",
        "src/xhs_local/cli.py",
        "src/xhs_local/website.py",
        "src/xhs_local/plugins/registry.py",
    }
    violations = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        if path.is_relative_to(PACKAGE_ROOT / "plugins"):
            continue
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        for imported in _absolute_imports(path):
            if (
                imported.startswith(("xhs_local.plugins.sources.", "xhs_local.plugins.sinks."))
                and relative not in allowed
            ):
                violations.append((relative, imported))
    assert violations == []
