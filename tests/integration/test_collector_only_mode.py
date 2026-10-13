import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from xhs_local.configuration.loader import load_snapshot
from xhs_local.plugins.sinks.xiaohongshu.plugin import XiaohongshuSinkPlugin


def test_xiaohongshu_submission_reaches_publisher():
    result = object()
    note = object()
    publisher = SimpleNamespace(publish=AsyncMock(return_value=result))
    sink = XiaohongshuSinkPlugin(publisher)
    assert asyncio.run(sink.publish(note, require_new_title_occurrence=True)) is result
    publisher.publish.assert_awaited_once_with(note, require_new_title_occurrence=True)


def test_agents_mode_cannot_fall_back_to_legacy_pipeline(monkeypatch):
    from xhs_local import app, website
    snapshot = SimpleNamespace(app=SimpleNamespace(
        agents=SimpleNamespace(enabled=True), website=SimpleNamespace(enabled=False)
    ))
    monkeypatch.setattr(app, "load_snapshot", lambda _: snapshot)
    website_run = AsyncMock()
    legacy_create = AsyncMock(side_effect=AssertionError("Legacy publishing must not start"))
    monkeypatch.setattr(website, "run_website", website_run)
    asyncio.run(app.run_application())
    website_run.assert_awaited_once_with(snapshot)
    legacy_create.assert_not_called()




def test_deployed_config_uses_xiaohongshu_pipeline():
    from pathlib import Path
    snapshot = load_snapshot(Path(__file__).resolve().parents[2] / "config")
    assert not snapshot.app.agents.enabled
    assert snapshot.app.website.enabled
    assert snapshot.publishing.sinks.xiaohongshu.enabled
    assert not any(r.enabled for r in snapshot.publishing.routes)
