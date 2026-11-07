"""Owner reading preferences with strict validation and optimistic concurrency."""

from __future__ import annotations

import json
from typing import Any

from .models import now_iso

DEFAULT_SETTINGS = {
    "hide_read": False,
    "retention_days": 7,
    "retention_mode": "archive",
    "retention_basis": "first_ingested",
    "retain_bookmarks": True,
    "auto_mark_read": True,
    "show_images": True,
    "default_sort": "importance",
    "default_view": "globe",
    "default_section": "feed",
    "density": "comfortable",
}
READ_ONLY_SETTINGS = {"retention_mode"}
SETTING_ENUMS = {
    "retention_basis": {"first_ingested", "published"},
    "default_sort": {"importance", "event_time", "discovered"},
    "default_view": {"globe", "list", "cards", "timeline"},
    "default_section": {"feed", "radar"},
    "density": {"comfortable", "compact"},
}


class ProductError(ValueError):
    """A safe, actionable API error, without infrastructure or credential details."""

    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(code)
        self.code = code
        self.message = message
        self.status = status


def validate_version(value: Any) -> int:
    if type(value) is not int or value < 1:
        raise ProductError("version_required", "缺少有效版本，请刷新后重试")
    return value


def validate_days(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= 3650:
        raise ProductError("invalid_retention_days", "保留窗口应为 1–3650 天，或 0 表示全部历史")
    return value


def validate_patch(value: Any) -> dict:
    if not isinstance(value, dict) or not value:
        raise ProductError("invalid_settings", "请提供需要保存的设置")
    for key, item in value.items():
        if key not in DEFAULT_SETTINGS:
            raise ProductError("unknown_setting", "请求包含不支持的设置")
        if key in READ_ONLY_SETTINGS:
            raise ProductError("read_only_setting", "归档方式与时间口径为只读说明")
        if key in SETTING_ENUMS:
            if not isinstance(item, str) or item not in SETTING_ENUMS[key]:
                raise ProductError("invalid_setting", "设置值不在支持范围内")
        elif key == "retention_days":
            validate_days(item)
        elif type(item) is not bool:
            raise ProductError("invalid_setting", "开关设置必须为 true 或 false")
    return dict(value)


class Preferences:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def _read(c, owner: str) -> dict:
        row = c.execute("SELECT data,version FROM preferences WHERE owner=?", (owner,)).fetchone()
        if row is None:
            return {"settings": dict(DEFAULT_SETTINGS), "version": 1}
        # Forward-compatible defaults without silently discarding existing user choices.
        saved = json.loads(row["data"])
        settings = {**DEFAULT_SETTINGS, **{k: v for k, v in saved.items() if k in DEFAULT_SETTINGS}}
        settings.update({k: DEFAULT_SETTINGS[k] for k in READ_ONLY_SETTINGS})
        return {"settings": settings, "version": row["version"]}

    def get(self, owner: str = "owner") -> dict:
        with self.store.connect() as c:
            return self._read(c, owner)

    def update(self, owner: str, patch: Any, version: Any) -> dict:
        checked = validate_patch(patch)
        version = validate_version(version)
        with self.store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            current = self._read(c, owner)
            if current["version"] != version:
                raise ProductError("settings_conflict", "设置已在其他窗口更新，请刷新后再保存", 409)
            settings = {**current["settings"], **checked}
            # Repeating an identical successful write is a no-op, not a revision churn.
            if settings == current["settings"]:
                return current
            next_version = version + 1
            c.execute(
                "INSERT INTO preferences(owner,data,version,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(owner) DO UPDATE SET data=excluded.data,"
                "version=excluded.version,updated_at=excluded.updated_at",
                (owner, json.dumps(settings, ensure_ascii=False), next_version, now_iso()),
            )
            c.execute(
                "INSERT INTO audit(at,owner,action,details) VALUES(?,?,?,?)",
                (now_iso(), owner, "preferences.updated", json.dumps({"fields": sorted(checked)})),
            )
        return {"settings": settings, "version": next_version}
