import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from xhs_local.configuration.loader import load_snapshot
from xhs_local.core.errors import PolicyRejected
from xhs_local.plugins.sinks.xiaohongshu.plugin import XiaohongshuSinkPlugin


def test_xiaohongshu_submission_is_rejected_before_browser():
    publisher = SimpleNamespace(publish=AsyncMock())
    sink = XiaohongshuSinkPlugin(publisher)
    with pytest.raises(PolicyRejected, match="disabled") as error:
        asyncio.run(sink.publish(object()))
    assert error.value.code == "XIAOHONGSHU_PUBLISHING_DISABLED"
    publisher.publish.assert_not_called()


def test_agents_mode_cannot_fall_back_to_legacy_pipeline(monkeypatch):
    from xhs_local import app, website
    snapshot = SimpleNamespace(app=SimpleNamespace(
        agents=SimpleNamespace(enabled=True), website=SimpleNamespace(enabled=False)
    ))
    monkeypatch.setattr(app, "load_snapshot", lambda _: snapshot)
    website_run = AsyncMock()
    legacy_create = AsyncMock(side_effect=AssertionError("Legacy publishing must not start"))
    monkeypatch.setattr(website, "run_website", website_run)
    monkeypatch.setattr(app.LocalApplication, "create", legacy_create)
    asyncio.run(app.run_application())
    website_run.assert_awaited_once_with(snapshot)
    legacy_create.assert_not_called()


def test_direct_legacy_start_is_blocked_for_agents_mode(monkeypatch, tmp_path):
    from xhs_local import app
    snapshot = SimpleNamespace(app=SimpleNamespace(agents=SimpleNamespace(enabled=True)))
    monkeypatch.setattr(app, "load_snapshot", lambda _: snapshot)
    with pytest.raises(PolicyRejected, match="cannot start"):
        asyncio.run(app.LocalApplication.create(tmp_path))
    assert not list(tmp_path.iterdir())


def test_deployed_config_has_no_xiaohongshu_publish_route():
    from pathlib import Path
    snapshot = load_snapshot(Path(__file__).resolve().parents[2] / "config")
    assert snapshot.app.agents.enabled
    assert not snapshot.publishing.sinks.xiaohongshu.enabled
    assert not any(r.enabled and "xiaohongshu" in r.sinks for r in snapshot.publishing.routes)
