"""Manifest-driven discovery, validation, and construction of source plugins."""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from .contracts import (
    HealthReport,
    NoteSinkPlugin,
    PluginContractError,
    PluginTarget,
    SinkPlugin,
    SourcePlugin,
    SourcePluginContext,
    UploadShareSinkPlugin,
)

MANIFEST_FIELDS = {
    "id",
    "kind",
    "api_version",
    "version",
    "entrypoint",
    "content_types",
    "source_options",
    "target_options",
}
SINK_MANIFEST_FIELDS = {
    "id",
    "kind",
    "api_version",
    "version",
    "entrypoint",
    "capabilities",
}
SUPPORTED_VALUE_TYPES = {"string", "integer", "number", "boolean"}


@dataclass(frozen=True, slots=True)
class SourceManifest:
    plugin_id: str
    version: int
    entrypoint: str
    content_types: tuple[str, ...]
    source_options: Mapping[str, Any]
    target_options: Mapping[str, Any]
    path: Path


@dataclass(frozen=True, slots=True)
class PreparedSource:
    manifest: SourceManifest
    plugin_class: type
    context: SourcePluginContext
    targets: tuple[PluginTarget, ...]


@dataclass(frozen=True, slots=True)
class PreflightReport:
    plugin_id: str
    ok: bool
    checks: tuple[str, ...]
    health: tuple[HealthReport, ...] = ()


@dataclass(frozen=True, slots=True)
class SinkManifest:
    plugin_id: str
    version: int
    entrypoint: str
    capabilities: tuple[str, ...]
    path: Path


def _as_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        result = dump(mode="python")
        if isinstance(result, Mapping):
            return dict(result)
    raise PluginContractError(f"{label} must be an object")


def _read_schema(value: Any, *, label: str) -> dict[str, Any]:
    schema = _as_mapping(value, label=label)
    allowed = {"required", "properties", "additional_properties"}
    unknown = set(schema) - allowed
    if unknown:
        raise PluginContractError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    additional = schema.get("additional_properties", False)
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise PluginContractError(f"{label}.required must be an array of names")
    if not isinstance(properties, Mapping):
        raise PluginContractError(f"{label}.properties must be an object")
    if not isinstance(additional, bool):
        raise PluginContractError(f"{label}.additional_properties must be boolean")
    if not set(required).issubset(properties):
        raise PluginContractError(f"{label}.required references an unknown property")
    normalized_properties: dict[str, dict[str, Any]] = {}
    for name, raw_rule in properties.items():
        if not isinstance(name, str) or not name:
            raise PluginContractError(f"{label} property names must be non-empty strings")
        rule = _as_mapping(raw_rule, label=f"{label}.{name}")
        allowed_rule = {"type", "minimum", "maximum", "format", "default"}
        unknown_rule = set(rule) - allowed_rule
        if unknown_rule:
            raise PluginContractError(
                f"{label}.{name} has unknown fields: {', '.join(sorted(unknown_rule))}"
            )
        if rule.get("type") not in SUPPORTED_VALUE_TYPES:
            raise PluginContractError(f"{label}.{name}.type is unsupported")
        if rule.get("format") not in {None, "path", "existing_file", "existing_directory"}:
            raise PluginContractError(f"{label}.{name}.format is unsupported")
        normalized_properties[name] = rule
    return {
        "required": tuple(required),
        "properties": MappingProxyType(normalized_properties),
        "additional_properties": additional,
    }


def _validate_value(value: Any, rule: Mapping[str, Any], *, label: str) -> Any:
    expected = rule["type"]
    if expected == "string":
        valid = isinstance(value, str) and bool(value.strip())
    elif expected == "integer":
        valid = isinstance(value, int) and not isinstance(value, bool)
    elif expected == "number":
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
    else:
        valid = isinstance(value, bool)
    if not valid:
        raise PluginContractError(f"{label} must be {expected}")
    if expected in {"integer", "number"}:
        if "minimum" in rule and value < rule["minimum"]:
            raise PluginContractError(f"{label} must be at least {rule['minimum']}")
        if "maximum" in rule and value > rule["maximum"]:
            raise PluginContractError(f"{label} must be at most {rule['maximum']}")
    return value.strip() if expected == "string" else value


def validate_options(
    values: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    label: str,
    base_path: Path | None = None,
) -> dict[str, Any]:
    """Apply the deliberately small manifest schema used by local plugins."""

    result = dict(values)
    properties = schema["properties"]
    unknown = set(result) - set(properties)
    if unknown and not schema["additional_properties"]:
        raise PluginContractError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")
    missing = set(schema["required"]) - set(result)
    if missing:
        raise PluginContractError(f"{label} is missing: {', '.join(sorted(missing))}")
    for name, rule in properties.items():
        if name not in result:
            if "default" in rule:
                result[name] = rule["default"]
            else:
                continue
        result[name] = _validate_value(result[name], rule, label=f"{label}.{name}")
        if rule.get("format") in {"path", "existing_file", "existing_directory"}:
            path = Path(result[name]).expanduser()
            if not path.is_absolute():
                if base_path is None:
                    raise PluginContractError(f"{label}.{name} needs a path base")
                path = base_path / path
            path = path.resolve()
            if rule.get("format") == "existing_file" and not path.is_file():
                raise PluginContractError(f"{label}.{name} is not an existing file: {path}")
            if rule.get("format") == "existing_directory" and not path.is_dir():
                raise PluginContractError(f"{label}.{name} is not an existing directory: {path}")
            result[name] = str(path)
    return result


def load_manifest(path: str | Path) -> SourceManifest:
    origin = Path(path).expanduser().resolve()
    try:
        raw = yaml.safe_load(origin.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise PluginContractError(f"{origin}: cannot read manifest: {error}") from error
    manifest = _as_mapping(raw, label=str(origin))
    unknown = set(manifest) - MANIFEST_FIELDS
    missing = MANIFEST_FIELDS - set(manifest)
    if missing or unknown:
        detail = []
        if missing:
            detail.append(f"missing {', '.join(sorted(missing))}")
        if unknown:
            detail.append(f"unknown {', '.join(sorted(unknown))}")
        raise PluginContractError(f"{origin}: invalid manifest ({'; '.join(detail)})")
    plugin_id = manifest["id"]
    if not isinstance(plugin_id, str) or not plugin_id or plugin_id != origin.parent.name:
        raise PluginContractError(f"{origin}: id must match its directory name")
    if manifest["kind"] != "source" or manifest["api_version"] != 1:
        raise PluginContractError(f"{origin}: unsupported kind or api_version")
    version = manifest["version"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise PluginContractError(f"{origin}: version must be a positive integer")
    entrypoint = manifest["entrypoint"]
    if not isinstance(entrypoint, str) or entrypoint.count(":") != 1:
        raise PluginContractError(f"{origin}: entrypoint must be module:class")
    module_name, class_name = entrypoint.split(":", 1)
    expected_prefix = f"xhs_local.plugins.sources.{plugin_id}."
    if not module_name.startswith(expected_prefix) or not class_name.isidentifier():
        raise PluginContractError(f"{origin}: entrypoint must stay inside its plugin package")
    content_types = manifest["content_types"]
    if (
        not isinstance(content_types, list)
        or not content_types
        or not all(isinstance(item, str) and item for item in content_types)
        or len(content_types) != len(set(content_types))
    ):
        raise PluginContractError(f"{origin}: content_types must be unique non-empty strings")
    return SourceManifest(
        plugin_id=plugin_id,
        version=version,
        entrypoint=entrypoint,
        content_types=tuple(content_types),
        source_options=_read_schema(manifest["source_options"], label="source_options"),
        target_options=_read_schema(manifest["target_options"], label="target_options"),
        path=origin,
    )


def load_sink_manifest(path: str | Path) -> SinkManifest:
    origin = Path(path).expanduser().resolve()
    try:
        raw = yaml.safe_load(origin.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise PluginContractError(f"{origin}: cannot read manifest: {error}") from error
    manifest = _as_mapping(raw, label=str(origin))
    unknown = set(manifest) - SINK_MANIFEST_FIELDS
    missing = SINK_MANIFEST_FIELDS - set(manifest)
    if missing or unknown:
        detail = []
        if missing:
            detail.append(f"missing {', '.join(sorted(missing))}")
        if unknown:
            detail.append(f"unknown {', '.join(sorted(unknown))}")
        raise PluginContractError(f"{origin}: invalid sink manifest ({'; '.join(detail)})")
    plugin_id = manifest["id"]
    if not isinstance(plugin_id, str) or not plugin_id or plugin_id != origin.parent.name:
        raise PluginContractError(f"{origin}: id must match its directory name")
    if manifest["kind"] != "sink" or manifest["api_version"] != 1:
        raise PluginContractError(f"{origin}: unsupported kind or api_version")
    version = manifest["version"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise PluginContractError(f"{origin}: version must be a positive integer")
    entrypoint = manifest["entrypoint"]
    if not isinstance(entrypoint, str) or entrypoint.count(":") != 1:
        raise PluginContractError(f"{origin}: entrypoint must be module:class")
    module_name, class_name = entrypoint.split(":", 1)
    expected_prefix = f"xhs_local.plugins.sinks.{plugin_id}."
    if not module_name.startswith(expected_prefix) or not class_name.isidentifier():
        raise PluginContractError(f"{origin}: entrypoint must stay inside its plugin package")
    capabilities = manifest["capabilities"]
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or not all(isinstance(item, str) and item for item in capabilities)
        or len(capabilities) != len(set(capabilities))
    ):
        raise PluginContractError(f"{origin}: capabilities must be unique non-empty strings")
    return SinkManifest(plugin_id, version, entrypoint, tuple(capabilities), origin)


def _load_plugin_class(manifest: SourceManifest) -> type:
    module_name, class_name = manifest.entrypoint.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        plugin_class = getattr(module, class_name)
    except (ImportError, AttributeError) as error:
        raise PluginContractError(
            f"{manifest.path}: cannot import {manifest.entrypoint}: {error}"
        ) from error
    if not inspect.isclass(plugin_class):
        raise PluginContractError(f"{manifest.path}: entrypoint is not a class")
    for method in ("validate_target", "healthcheck", "collect", "close"):
        if not callable(getattr(plugin_class, method, None)):
            raise PluginContractError(f"{manifest.path}: plugin lacks {method}()")
    return plugin_class


def _load_sink_class(manifest: SinkManifest) -> type:
    module_name, class_name = manifest.entrypoint.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        plugin_class = getattr(module, class_name)
    except (ImportError, AttributeError) as error:
        raise PluginContractError(
            f"{manifest.path}: cannot import {manifest.entrypoint}: {error}"
        ) from error
    if not inspect.isclass(plugin_class):
        raise PluginContractError(f"{manifest.path}: entrypoint is not a class")
    required = {"preflight", "close"}
    if "image_note" in manifest.capabilities:
        required.update(("publish", "reconcile"))
    if "upload" in manifest.capabilities:
        required.add("async_upload_and_share")
    for method in required:
        if not callable(getattr(plugin_class, method, None)):
            raise PluginContractError(f"{manifest.path}: sink plugin lacks {method}()")
    return plugin_class


def normalize_target(value: Any) -> PluginTarget:
    if isinstance(value, PluginTarget):
        return value
    raw = _as_mapping(value, label="target")
    options = raw.pop("options", {})
    required = {"id", "locator", "name"}
    ignored = {"enabled", "poll_seconds"}
    unknown = set(raw) - required - ignored
    if unknown or not required.issubset(raw):
        raise PluginContractError(
            "target requires only id, locator, name, enabled, poll_seconds, and options"
        )
    for key in required:
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise PluginContractError(f"target.{key} must be a non-empty string")
    return PluginTarget(
        id=raw["id"].strip(),
        locator=raw["locator"].strip(),
        name=raw["name"].strip(),
        options=MappingProxyType(_as_mapping(options, label="target.options")),
    )


class SourcePluginRegistry:
    """Discover built-in manifests without a platform switch statement."""

    def __init__(self, manifest_root: str | Path | None = None) -> None:
        self.manifest_root = (
            Path(manifest_root).expanduser().resolve()
            if manifest_root is not None
            else (Path(__file__).parent / "sources").resolve()
        )
        self._manifests: dict[str, SourceManifest] | None = None

    def discover(self) -> Mapping[str, SourceManifest]:
        manifests: dict[str, SourceManifest] = {}
        for path in sorted(self.manifest_root.glob("*/manifest.yaml")):
            manifest = load_manifest(path)
            if manifest.plugin_id in manifests:
                raise PluginContractError(f"duplicate source plugin {manifest.plugin_id}")
            manifests[manifest.plugin_id] = manifest
        self._manifests = manifests
        return MappingProxyType(dict(manifests))

    def manifest(self, plugin_id: str) -> SourceManifest:
        manifests = self._manifests if self._manifests is not None else self.discover()
        try:
            return manifests[plugin_id]
        except KeyError as error:
            raise PluginContractError(f"source plugin is not installed: {plugin_id}") from error

    def prepare(
        self,
        source_config: Any,
        *,
        config_root: str | Path,
        runtime_root: str | Path,
        log=None,
    ) -> PreparedSource:
        raw = _as_mapping(source_config, label="source")
        plugin_id = raw.get("plugin")
        source_id = raw.get("id")
        if not isinstance(plugin_id, str) or not isinstance(source_id, str):
            raise PluginContractError("source requires id and plugin")
        manifest = self.manifest(plugin_id)
        plugin_class = _load_plugin_class(manifest)
        target_values = raw.pop("targets", None)
        source_options = _as_mapping(raw.pop("options", {}), label="source.options")
        for field in ("id", "plugin", "enabled", "poll_seconds"):
            raw.pop(field, None)
        if raw:
            raise PluginContractError(
                f"source[{source_id}] has unknown fields: {', '.join(sorted(raw))}"
            )
        options = validate_options(
            source_options,
            manifest.source_options,
            label=f"source[{source_id}]",
            base_path=Path(config_root).resolve(),
        )
        disabled_targets: tuple[PluginTarget, ...] = ()
        if isinstance(target_values, Sequence) and not isinstance(target_values, (str, bytes)):
            target_pairs = tuple(
                (
                    normalize_target(value),
                    bool(_as_mapping(value, label="target").get("enabled", True)),
                )
                for value in target_values
            )
            targets = tuple(target for target, enabled in target_pairs if enabled)
            disabled_targets = tuple(target for target, enabled in target_pairs if not enabled)
        else:
            raise PluginContractError(f"source[{source_id}].targets must be an array")
        seen = set()
        active_ids = {target.id for target in targets}
        validated_targets = []
        for target in (*targets, *disabled_targets):
            if target.id in seen:
                raise PluginContractError(f"duplicate target ID {target.id}")
            seen.add(target.id)
            target_options = validate_options(
                target.options,
                manifest.target_options,
                label=f"target[{target.id}]",
                base_path=Path(config_root).resolve(),
            )
            target = PluginTarget(target.id, target.locator, target.name, target_options)
            plugin_class.validate_target(target)
            if target.id in active_ids:
                validated_targets.append(target)
        context = SourcePluginContext(
            source_id=source_id,
            runtime_root=Path(runtime_root).expanduser().resolve(),
            options=MappingProxyType(options),
            **({"log": log} if log is not None else {}),
        )
        return PreparedSource(manifest, plugin_class, context, tuple(validated_targets))

    @staticmethod
    def create(prepared: PreparedSource, **dependencies: Any) -> SourcePlugin:
        plugin = prepared.plugin_class(prepared.context, **dependencies)
        if not isinstance(plugin, SourcePlugin):
            raise PluginContractError(
                f"{prepared.manifest.plugin_id} instance violates SourcePlugin"
            )
        return plugin

    async def preflight(
        self,
        prepared: PreparedSource,
        *,
        healthcheck: bool = False,
        deadline: float | None = None,
        dependencies: Mapping[str, Any] | None = None,
    ) -> PreflightReport:
        checks = ["manifest", "import", "contract", "options", "targets"]
        reports: list[HealthReport] = []
        if healthcheck:
            plugin = self.create(prepared, **dict(dependencies or {}))
            try:
                for target in prepared.targets:
                    report = await plugin.healthcheck(target, deadline)
                    if not report.ok:
                        raise PluginContractError(
                            f"{prepared.manifest.plugin_id} healthcheck failed: {report.message}"
                        )
                    reports.append(report)
                checks.append("healthcheck")
            finally:
                await plugin.close()
        return PreflightReport(
            plugin_id=prepared.manifest.plugin_id,
            ok=True,
            checks=tuple(checks),
            health=tuple(reports),
        )


class SinkPluginRegistry:
    """Discover and construct sink adapters from their local manifests."""

    def __init__(self, manifest_root: str | Path | None = None) -> None:
        self.manifest_root = (
            Path(manifest_root).expanduser().resolve()
            if manifest_root is not None
            else (Path(__file__).parent / "sinks").resolve()
        )
        self._manifests: dict[str, SinkManifest] | None = None

    def discover(self) -> Mapping[str, SinkManifest]:
        manifests: dict[str, SinkManifest] = {}
        for path in sorted(self.manifest_root.glob("*/manifest.yaml")):
            manifest = load_sink_manifest(path)
            if manifest.plugin_id in manifests:
                raise PluginContractError(f"duplicate sink plugin {manifest.plugin_id}")
            manifests[manifest.plugin_id] = manifest
        self._manifests = manifests
        return MappingProxyType(dict(manifests))

    def prepare(self, plugin_id: str) -> tuple[SinkManifest, type]:
        manifests = self._manifests if self._manifests is not None else self.discover()
        try:
            manifest = manifests[plugin_id]
        except KeyError as error:
            raise PluginContractError(f"sink plugin is not installed: {plugin_id}") from error
        return manifest, _load_sink_class(manifest)

    @staticmethod
    def create(prepared: tuple[SinkManifest, type], **dependencies: Any) -> Any:
        manifest, plugin_class = prepared
        plugin = plugin_class(**dependencies)
        if not isinstance(plugin, SinkPlugin):
            raise PluginContractError(f"{manifest.plugin_id} violates SinkPlugin lifecycle")
        if "image_note" in manifest.capabilities and not isinstance(plugin, NoteSinkPlugin):
            raise PluginContractError(f"{manifest.plugin_id} violates NoteSinkPlugin")
        if "upload" in manifest.capabilities and not isinstance(plugin, UploadShareSinkPlugin):
            raise PluginContractError(f"{manifest.plugin_id} violates UploadShareSinkPlugin")
        return plugin

    async def preflight(
        self,
        prepared: tuple[SinkManifest, type],
        *,
        live: bool = False,
        dependencies: Mapping[str, Any] | None = None,
    ) -> PreflightReport:
        manifest, _plugin_class = prepared
        checks = ["manifest", "import", "contract", "capabilities"]
        reports: list[HealthReport] = []
        if live:
            plugin = self.create(prepared, **dict(dependencies or {}))
            try:
                report = await plugin.preflight()
                if not report.ok:
                    raise PluginContractError(
                        f"{manifest.plugin_id} preflight failed: {report.message}"
                    )
                reports.append(report)
                checks.append("healthcheck")
            finally:
                await plugin.close()
        return PreflightReport(manifest.plugin_id, True, tuple(checks), tuple(reports))
