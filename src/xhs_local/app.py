"""One collector runtime; the operating AI Agent owns writing and publication."""

from pathlib import Path

from xhs_local.configuration.loader import load_snapshot

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"


async def run_application(config_root: Path = CONFIG_ROOT) -> None:
    from xhs_local.website import run_website

    await run_website(load_snapshot(config_root))
