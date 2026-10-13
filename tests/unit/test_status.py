from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from xhs_local.observability.logging import JsonFormatter
from xhs_local.observability.status import StatusStore, read_status


def test_status_timestamps_use_configured_shanghai_timezone(tmp_path) -> None:
    path = tmp_path / "status.json"
    store = StatusStore(path, "Asia/Shanghai")
    store.update(ready=True)

    status = read_status(path)
    assert status is not None
    assert status["timezone"] == "Asia/Shanghai"
    assert datetime.fromisoformat(status["started_at"]).utcoffset() == timedelta(hours=8)
    assert datetime.fromisoformat(status["updated_at"]).utcoffset() == timedelta(hours=8)


def test_structured_log_timestamp_uses_beijing_timezone() -> None:
    record = logging.LogRecord("component", logging.INFO, __file__, 1, "event", (), None)
    payload = json.loads(JsonFormatter("Asia/Shanghai").format(record))

    assert datetime.fromisoformat(payload["timestamp"]).utcoffset() == timedelta(hours=8)
