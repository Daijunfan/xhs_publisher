from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from xhs_local.core.errors import ValidationFailure
from xhs_local.processing import transcription
from xhs_local.processing.transcription import LocalWhisperClient


def test_local_transcription_reuses_model_and_checks_complete_audio(tmp_path, monkeypatch):
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

    monkeypatch.setattr(transcription, "WhisperModel", Model)
    client = LocalWhisperClient(tmp_path / "model")

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
    assert loads[0][1] == {"device": "cuda", "compute_type": "float16"}
