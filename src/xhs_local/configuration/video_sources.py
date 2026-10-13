"""Import creator homepages and keep the supplied transcription key out of config."""

from __future__ import annotations

import os
import re
from pathlib import Path
from textwrap import indent
from urllib.parse import urlsplit

import yaml


def creator_target(url: str) -> tuple[str, dict[str, object]]:
    parsed = urlsplit(url)
    host, path = parsed.netloc.lower(), parsed.path.rstrip("/")
    if host in {"youtube.com", "www.youtube.com"}:
        match = re.fullmatch(r"/(?:@([\w.-]+)|channel/(UC[\w-]+)|(?:c/|user/)?([\w.-]+))", path)
        if not match or path in {"/watch", "/playlist", "/shorts", "/live", "/feed"}:
            raise ValueError("YouTube input must be a creator homepage, not a video")
        platform = "youtube"
        identity = next(value for value in match.groups() if value)
        canonical = f"https://www.youtube.com{path}"
    else:
        raise ValueError("unsupported creator homepage")
    return platform, {
        "id": f"{platform}-{identity.casefold()}",
        "locator": canonical,
        "name": identity,
        "enabled": True,
    }


def read_creator_document(path: Path) -> tuple[dict[str, list[dict[str, object]]], str]:
    text = path.read_text(encoding="utf-8")
    key = re.search(r"(?im)^\s*api\s*key\s*[:：]\s*(\S+)\s*$", text)
    if key is None:
        raise ValueError("creator document lacks a transcription API key")
    if "paraformer-v2" not in text.casefold():
        raise ValueError("creator document must specify the supported paraformer-v2 model")
    targets: dict[str, list[dict[str, object]]] = {"youtube": []}
    seen: set[str] = set()
    for url in re.findall(r"https?://[^\s)\]>]+", text):
        try:
            platform, target = creator_target(url)
        except ValueError:
            continue
        identity = str(target["id"])
        if identity not in seen:
            targets[platform].append(target)
            seen.add(identity)
    if not all(targets.values()):
        raise ValueError("creator document must contain YouTube homepages")
    return targets, key.group(1)


def import_creator_document(
    document: Path, config_root: Path, *, enabled: bool = False
) -> dict[str, int]:
    targets, key = read_creator_document(document)
    app = yaml.safe_load((config_root / "app.yaml").read_text(encoding="utf-8"))
    runtime = (config_root / app["runtime_root"]).resolve()
    secret = runtime / "secrets/dashscope-api-key"
    secret.parent.mkdir(parents=True, exist_ok=True)
    if secret.exists() and secret.read_text(encoding="utf-8").strip() != key:
        raise ValueError("existing transcription key differs; refusing to overwrite it")
    descriptor = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(key + "\n")
    secret.chmod(0o600)
    sources_path = config_root / "sources.yaml"
    original = sources_path.read_text(encoding="utf-8")
    config = yaml.safe_load(original)
    existing = {source["plugin"]: source for source in config["sources"]}
    for platform, entries in targets.items():
        if platform in existing:
            source = existing[platform]
            source["targets"] = entries
        else:
            config["sources"].append(
                {
                    "id": platform,
                    "plugin": platform,
                    "enabled": enabled,
                    "poll_seconds": 1800,
                    "options": {},
                    "targets": entries,
                }
            )
    tree = yaml.compose(original)
    sequence = next(value for key, value in tree.value if key.value == "sources")
    lines = original.splitlines(keepends=True)
    indentation = " " * max(0, sequence.value[0].start_mark.column - 2)
    replacements = []
    for node, source in zip(sequence.value, yaml.safe_load(original)["sources"], strict=True):
        if source["plugin"] in targets:
            updated = next(item for item in config["sources"] if item["id"] == source["id"])
            block = indent(
                yaml.safe_dump([updated], allow_unicode=True, sort_keys=False), indentation
            )
            replacements.append((node.start_mark.line, node.end_mark.line, block))
    for start, end, block in reversed(replacements):
        lines[start:end] = [block]
    text = "".join(lines)
    for source in config["sources"]:
        if source["plugin"] not in existing:
            text = (
                text.rstrip()
                + "\n"
                + indent(yaml.safe_dump([source], allow_unicode=True, sort_keys=False), indentation)
            )
    sources_path.write_text(text, encoding="utf-8")
    return {platform: len(entries) for platform, entries in targets.items()}
