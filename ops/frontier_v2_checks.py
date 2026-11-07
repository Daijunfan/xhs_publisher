#!/usr/bin/env python3
"""Run review gates in the isolated candidate without network collectors or model calls."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["contract", "regression"], default="contract")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    # Preserve an explicitly supplied isolated dependency path while keeping
    # project source first. Useful on macOS where the local test venv may be
    # intentionally leaner than the fully provisioned cloud production venv.
    inherited = os.environ.get("PYTHONPATH", "")
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, (str(root / "src"), inherited)))}
    if args.phase == "contract":
        command = [sys.executable, "-m", "unittest", "discover", "-s", "tests/frontier", "-v"]
    else:
        command = [sys.executable, "-m", "pytest", "-q",
                   "tests/unit/plugins/sources/test_x.py",
                   "tests/unit/plugins/sources/test_video.py",
                   "tests/unit/plugins/sources/test_telegram.py",
                   "tests/unit/pipeline/test_source_cadence.py",
                   "tests/integration/test_website_videos.py",
                   "tests/architecture/test_directory_contract.py",
                   "tests/architecture/test_import_boundaries.py",
                   "tests/architecture/test_package_data.py"]
    raise SystemExit(subprocess.run(command, cwd=root, env=environment).returncode)


if __name__ == "__main__":
    main()
