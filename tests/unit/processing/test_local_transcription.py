from __future__ import annotations

import asyncio
import importlib.util
import sys
from types import SimpleNamespace

import pytest

from xhs_local.core.errors import ValidationFailure
from xhs_local.processing import transcription
from xhs_local.processing.transcription import LocalWhisperClient


@pytest.mark.parametrize("device,threads", [("cuda", 0), ("cpu", 8)])
def test_local_transcription_reuses_model_and_checks_complete_audio(tmp_path, device, threads):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"sample")
    loads = []

    class Model:
        def __init__(self, path, **options):
            loads.append((path, options))

        def transcribe(self, path, **options):
            assert path == str(audio.resolve())
            assert options["vad_filter"] is False
            return iter([SimpleNamespace(text=" hello "), SimpleNamespace(text=" world ")]), (
                SimpleNamespace(duration=10.0, language="en")
            )

    client = LocalWhisperClient(tmp_path / "model", device=device, model_factory=Model)

    async def run():
        task_id = await client.submit(await client.upload(audio))
        result = await client.result(task_id, expected_duration=10.0)
        assert result["text"] == "hello\n\nworld"
        assert result["duration"] == 10.0
        assert result["raw"]["language"] == "en"
        with pytest.raises(ValidationFailure):
            await client.result(task_id, expected_duration=2.0)

    asyncio.run(run())
    assert len(loads) == 1
    assert loads[0][1] == {
        "device": device,
        "compute_type": "float16",
        "cpu_threads": threads,
    }


def test_cloud_transcription_does_not_require_the_local_model_dependency(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    spec = importlib.util.spec_from_file_location("isolated_transcription", transcription.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client = module.ParaformerClient(tmp_path / "key", request=lambda *_: None)
    assert client.model == "paraformer-v2"
