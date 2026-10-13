"""Restore the separately transferred credentials into their existing runtime paths."""

import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
bundle = Path(sys.argv[1] if len(sys.argv) > 1 else root / "Sensitive data").resolve()
required = [
    ".env",
    "runtime/sessions/telegram-user.session",
    "runtime/secrets/youtube-browser-e7be810d639e.txt",
    "runtime/secrets/xiaohongshu-chromium.json",
    "runtime/secrets/operator-api.token",
]
missing = [name for name in required if not (bundle / name).is_file()]
if missing:
    raise SystemExit("Sensitive data is incomplete: " + ", ".join(missing))

files = [bundle / ".env"]
for directory in ("runtime/secrets", "runtime/sessions"):
    files.extend(
        path for path in (bundle / directory).rglob("*")
        if path.is_file() and not path.name.startswith("._")
    )
for source in files:
    destination = root / source.relative_to(bundle)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.parent != root:
        destination.parent.chmod(0o700)
    shutil.copyfile(source, destination)
    destination.chmod(0o600)
print(f"Restored {len(files)} credential files. Start with ops/run_cloud.sh or systemd.")
