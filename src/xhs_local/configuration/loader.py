"""Load all configuration files into one immutable validated snapshot."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import AppConfig, PublishingConfig, SourcesConfig


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ConfigSnapshot:
    revision: str
    config_root: Path
    app: AppConfig
    sources: SourcesConfig
    publishing: PublishingConfig

    def resolve(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path.resolve() if path.is_absolute() else (self.config_root / path).resolve()

    @property
    def runtime_root(self) -> Path:
        return self.resolve(self.app.runtime_root)

    @property
    def database_path(self) -> Path:
        return self.resolve(self.app.database_path)


def _read_yaml(path: Path) -> object:
    try:
        with path.open(encoding="utf-8") as stream:
            return yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as error:
        raise ConfigurationError(f"{path}: cannot read YAML: {error}") from error


def load_snapshot(config_root: str | Path) -> ConfigSnapshot:
    root = Path(config_root).expanduser().resolve()
    data = {
        "app": _read_yaml(root / "app.yaml"),
        "sources": _read_yaml(root / "sources.yaml"),
        "publishing": _read_yaml(root / "publishing.yaml"),
    }
    return snapshot_from_data(root, data)


def snapshot_from_data(config_root: str | Path, data: dict[str, object]) -> ConfigSnapshot:
    root = Path(config_root).expanduser().resolve()
    try:
        app = AppConfig.model_validate(data["app"])
        sources = SourcesConfig.model_validate(data["sources"])
        publishing = PublishingConfig.model_validate(data["publishing"])
    except KeyError as error:
        raise ConfigurationError(f"configuration snapshot lacks {error.args[0]}") from error
    except ValidationError as error:
        raise ConfigurationError(str(error)) from error

    canonical = {
        "app": app.model_dump(mode="json"),
        "sources": sources.model_dump(mode="json"),
        "publishing": publishing.model_dump(mode="json"),
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    revision = hashlib.sha256(encoded.encode()).hexdigest()
    return ConfigSnapshot(revision, root, app, sources, publishing)


def snapshot_data(snapshot: ConfigSnapshot) -> dict[str, object]:
    return {
        "app": snapshot.app.model_dump(mode="json"),
        "sources": snapshot.sources.model_dump(mode="json"),
        "publishing": snapshot.publishing.model_dump(mode="json"),
    }
