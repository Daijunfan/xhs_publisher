"""Stable identifiers and content hashes."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping


def new_id() -> str:
    return str(uuid.uuid4())


def stable_record_id(source_id: str, target_id: str, external_id: str) -> str:
    raw = f"{source_id}\0{target_id}\0{external_id}".encode()
    return hashlib.sha256(raw).hexdigest()


def content_hash(value: Mapping | list | str | bytes) -> str:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        raw = value.encode()
    else:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()
