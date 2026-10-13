from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _uv() -> str:
    project_uv = ROOT / ".venv/bin/uv"
    if project_uv.is_file():
        return str(project_uv)
    executable = shutil.which("uv")
    assert executable, "offline wheel verification requires uv"
    return executable


def test_wheel_contains_runtime_templates_scripts_manifests_and_migrations(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    shutil.copy2(ROOT / "pyproject.toml", project / "pyproject.toml")
    shutil.copytree(ROOT / "src", project / "src", ignore=shutil.ignore_patterns("__pycache__"))
    output = tmp_path / "wheelhouse"
    result = subprocess.run(
        [_uv(), "build", "--wheel", "--offline", "--out-dir", str(output)],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, f"wheel build failed:\n{result.stdout}\n{result.stderr}"
    wheels = list(output.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as wheel:
        names = set(wheel.namelist())
        expected = {
            "xhs_local/rendering/templates/news_with_media.html",
            "xhs_local/rendering/templates/news_text_editorial.html",
            "xhs_local/rendering/templates/x_post.html",
            "xhs_local/rendering/templates/website.html",
            "xhs_local/plugins/sinks/xiaohongshu/manifest.yaml",
            "xhs_local/plugins/sources/telegram/manifest.yaml",
            "xhs_local/plugins/sources/x/manifest.yaml",
            "xhs_local/plugins/sources/youtube/manifest.yaml",
            "xhs_local/storage/migrations/001_initial.sql",
            "xhs_local/storage/migrations/002_work_outbox.sql",
            "xhs_local/storage/migrations/003_config_dlq_retention.sql",
            "xhs_local/storage/migrations/004_news_favorites.sql",
            "xhs_local/storage/migrations/005_news_deleted.sql",
        }
        assert expected <= names
        assert not any(
            "/local_documents/" in name or "/baidu/" in name or name.endswith("resource_link.html")
            for name in names
        )
        assert not any(name.endswith((".pyc", ".pyo")) or "__pycache__" in name for name in names)
        entry_points = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
        assert "xhs = xhs_local.cli:main" in wheel.read(entry_points).decode()


def test_project_declares_one_python_runtime_and_lock() -> None:
    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.12"' in metadata
    assert (ROOT / "uv.lock").is_file()
    assert 'xhs = "xhs_local.cli:main"' in metadata
    assert "node" not in metadata.lower()
    assert sys.version_info >= (3, 12)
