"""Reuse the existing Telegram offline transport fixture to prove no eager full-file IO."""
import asyncio
import importlib.util
import os
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from xhs_local.plugins.contracts import PluginTarget


def test_metadata_only_never_downloads_document_or_generated_preview(tmp_path):
    root = Path(os.environ.get("AEXUS_XHS_ROOT", str(Path(__file__).resolve().parents[2])))
    spec = importlib.util.spec_from_file_location("telegram_transport_fixtures", root / "tests/unit/plugins/sources/test_telegram.py")
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    message = SimpleNamespace(id=500, message="Foreign magazine", date=datetime(2026, 8, 19, 4, 30, tzinfo=UTC), grouped_id=None, photo=None, document=SimpleNamespace(id=987), file=SimpleNamespace(name="Magazine.pdf", mime_type="application/pdf", size=8000000))
    client = helpers.FakeTelegramClient([message])
    plugin = helpers._plugin(tmp_path, client)
    downloads = []

    async def forbidden(*args, **kwargs):
        downloads.append(True)
        raise AssertionError("Listing must not fetch the magazine or a generated full-file preview")

    plugin.transport.download_document = forbidden
    plugin.transport.document_preview = forbidden
    target = PluginTarget("magazines", "fixture_magazines", "Magazines", {"collect_documents": True, "document_metadata_only": True})
    result = asyncio.run(plugin.collect(helpers._request(target)))
    asyncio.run(plugin.close())
    assert downloads == []
    assert len(result.records) == 1
    record = result.records[0]
    assert record.title == "Magazine.pdf"
    assert record.attachments == ()
    assert record.payload["deferred_files"] == [{"id": "tg-500-987", "name": "Magazine.pdf", "mimeType": "application/pdf", "bytes": 8000000, "deferred": True}]
