"""Shared JSON extraction and response index parsing."""

# Prompt wording is an external behavior contract and must not be line-wrapped.
# ruff: noqa: E501

from __future__ import annotations

import json
import math
import re
from typing import Any

from .provider import DeepSeekResponseError


def extract_json(content: str) -> dict[str, Any]:
    text = str(content or "").strip()
    if not text:
        raise DeepSeekResponseError("DeepSeek returned empty content")
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    candidate = fenced.group(1).strip() if fenced else text
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end <= start:
            raise DeepSeekResponseError("DeepSeek response contains no JSON object") from None
        try:
            payload = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as error:
            raise DeepSeekResponseError("DeepSeek response JSON is malformed") from error
    if not isinstance(payload, dict):
        raise DeepSeekResponseError("DeepSeek response JSON is not an object")
    return payload


def js_number(value: object) -> float:
    """The JSON-value subset of JavaScript's Number() coercion."""

    if value is None:
        return 0.0
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0.0
        try:
            if stripped.lower().startswith(("0x", "+0x", "-0x")):
                sign = -1 if stripped.startswith("-") else 1
                unsigned = stripped.removeprefix("+").removeprefix("-")
                return float(sign * int(unsigned, 16))
            return float(stripped)
        except ValueError:
            return math.nan
    return math.nan
