from __future__ import annotations

import ast
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src/xhs_local"


def test_pyproject_exposes_one_python_application_entrypoint() -> None:
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["requires-python"].startswith(">=3.12")
    assert project["project"]["scripts"] == {"xhs": "xhs_local.cli:main"}
    assert project["tool"]["setuptools"]["package-dir"] == {"": "src"}
    main_module = ast.parse((SOURCE_ROOT / "__main__.py").read_text(encoding="utf-8"))
    imports = [node for node in ast.walk(main_module) if isinstance(node, ast.ImportFrom)]
    assert [(node.module, [alias.name for alias in node.names]) for node in imports] == [
        ("cli", ["main"])
    ]


def test_production_package_has_no_node_runtime_entrypoint() -> None:
    assert not (PROJECT_ROOT / "backend").exists()
    assert not (PROJECT_ROOT / "package.json").exists()
    assert not (PROJECT_ROOT / "package-lock.json").exists()
    forbidden = [
        path
        for path in SOURCE_ROOT.rglob("*")
        if path.is_file()
        and (path.suffix in {".mjs", ".cjs", ".ts"} or path.name == "package.json")
    ]
    scripts = sorted(SOURCE_ROOT.rglob("*.js"))

    assert forbidden == []
    assert scripts == []
    # yt-dlp may run its own YouTube JS extractor. This is a media-tool dependency,
    # not a second application, hand-written JS service, or Node publication runtime.
    video_adapter = SOURCE_ROOT / "plugins/sources/video/client.py"
    python_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in SOURCE_ROOT.rglob("*.py")
        if path not in {video_adapter, SOURCE_ROOT / "plugins/sources/youtube/client.py"}
    )
    assert '"node"' not in python_text
    assert '"npm"' not in python_text
    assert '"--js-runtimes"' in video_adapter.read_text(encoding="utf-8")


def test_platform_names_do_not_leak_into_pipeline_or_storage() -> None:
    for boundary in (SOURCE_ROOT / "pipeline", SOURCE_ROOT / "storage"):
        text = "\n".join(
            path.read_text(encoding="utf-8").casefold() for path in boundary.rglob("*.py")
        )
        for platform in ("telegram", "safari", "baidu", "xiaohongshu"):
            assert platform not in text
