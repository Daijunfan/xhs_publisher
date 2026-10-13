"""Creator-link normalization and atomic updates to the existing source config."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

from .models import SourcesConfig, TargetConfig
from .video_sources import creator_target


def parse_creator_link(value: str) -> tuple[str, TargetConfig]:
    value = value.strip()
    parsed = urlsplit(value if "://" in value else f"https://{value}")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("请输入 X 或 YouTube 博主主页链接")
    host = parsed.netloc.lower()
    path = unquote(parsed.path).rstrip("/")
    if host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}:
        handle = path.removeprefix("/").removeprefix("@")
        if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle) or handle.lower() in {
            "home",
            "explore",
            "search",
            "settings",
            "notifications",
            "messages",
            "i",
            "intent",
            "share",
            "login",
            "signup",
            "compose",
        }:
            raise ValueError("X 链接必须是博主主页，不能是单条帖子或功能页面")
        return "x", TargetConfig(id=f"x-{handle.lower()}", locator=handle, name=handle)
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        path = re.sub(r"/(videos|shorts|streams|featured|about|playlists|community)$", "", path)
        try:
            platform, target = creator_target(f"https://www.youtube.com{path}")
        except ValueError:
            raise ValueError("YouTube 链接必须是频道主页，不能是单个视频") from None
        return platform, TargetConfig.model_validate(target)
    raise ValueError("仅支持 X 和 YouTube 博主主页链接")



def collector_locator(platform: str, locator: str) -> str:
    """Use existing homepage parsing to prepare Core's public forms for collectors."""
    if platform not in {"x", "youtube"}:
        return locator
    value = locator.strip()
    if platform == "x" and re.fullmatch(r"@?[A-Za-z0-9_]{1,15}", value):
        value = "https://x.com/" + value.removeprefix("@")
    elif platform == "youtube" and value.startswith("@"):
        value = "https://www.youtube.com/" + value
    found, target = parse_creator_link(value)
    if found != platform:
        raise ValueError("Core subscription locator does not match its source platform")
    return target.locator


def creator_key(platform: str, locator: str) -> str:
    url = f"https://x.com/{locator.removeprefix('@')}" if platform == "x" else locator
    return parse_creator_link(url)[1].locator.casefold()


def save_sources(config_root: Path, sources: SourcesConfig) -> None:
    path = config_root / "sources.yaml"
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            yaml.safe_dump(sources.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        temporary.chmod(path.stat().st_mode & 0o777)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def source_homepage(platform: str, locator: str) -> str:
    locator = collector_locator(platform, locator)
    if locator.startswith(("https://", "http://")):
        return locator
    base = {"x": "https://x.com/", "telegram": "https://t.me/"}.get(platform, "")
    return base + locator.removeprefix("@")
