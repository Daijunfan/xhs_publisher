"""Cloud Paraformer and local Whisper transcription implementations."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

import requests
from faster_whisper import WhisperModel

from xhs_local.core.errors import AuthenticationRequired, TransientError, ValidationFailure


class TranscriptionTaskFailed(ValidationFailure):
    """A terminal cloud attempt can be retried from its already downloaded audio."""


class ParaformerClient:
    def __init__(
        self,
        key_path: Path,
        *,
        base_url: str = "https://dashscope.aliyuncs.com/api/v1",
        model: str = "paraformer-v2",
        request=None,
    ) -> None:
        self.key_path = key_path
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.request = request or requests.request

    def headers(self) -> dict[str, str]:
        try:
            key = self.key_path.read_text(encoding="utf-8").strip()
        except OSError:
            raise AuthenticationRequired("configure the DashScope key in runtime/secrets") from None
        if not key:
            raise AuthenticationRequired("DashScope key is empty")
        return {"Authorization": f"Bearer {key}"}

    async def _request(self, method: str, url: str, **kwargs) -> Any:
        try:
            response = await asyncio.to_thread(self.request, method, url, timeout=90, **kwargs)
        except requests.RequestException:
            raise TransientError(
                "DashScope connection failed; saved audio and task are retained"
            ) from None
        if response.status_code in {401, 403}:
            raise AuthenticationRequired("DashScope rejected the key or model permission")
        if response.status_code >= 400:
            raise TransientError(
                f"DashScope HTTP {response.status_code}", code=str(response.status_code)
            )
        return response

    async def upload(self, audio: Path) -> str:
        response = await self._request(
            "GET",
            self.base_url + "/uploads",
            headers=self.headers(),
            params={"action": "getPolicy", "model": self.model},
        )
        policy = response.json()["data"]
        object_key = f"{policy['upload_dir']}/{uuid.uuid4().hex}-{audio.name}"
        fields = {
            "OSSAccessKeyId": policy["oss_access_key_id"],
            "Signature": policy["signature"],
            "policy": policy["policy"],
            "x-oss-object-acl": policy["x_oss_object_acl"],
            "x-oss-forbid-overwrite": policy["x_oss_forbid_overwrite"],
            "key": object_key,
            "success_action_status": "200",
        }
        with audio.open("rb") as stream:
            await self._request(
                "POST", policy["upload_host"], data=fields, files={"file": (audio.name, stream)}
            )
        return f"oss://{object_key}"

    async def submit(self, audio_url: str) -> str:
        response = await self._request(
            "POST",
            self.base_url + "/services/audio/asr/transcription",
            headers={
                **self.headers(),
                "X-DashScope-Async": "enable",
                "X-DashScope-OssResourceResolve": "enable",
            },
            json={
                "model": self.model,
                "input": {"file_urls": [audio_url]},
                "parameters": {"channel_id": [0], "language_hints": ["zh", "en"]},
            },
        )
        task_id = response.json().get("output", {}).get("task_id")
        if not task_id:
            raise TransientError("DashScope returned no transcription task ID")
        return task_id

    async def result(self, task_id: str, *, expected_duration: float) -> dict[str, Any] | None:
        try:
            response = await self._request(
                "POST", self.base_url + f"/tasks/{task_id}", headers=self.headers()
            )
        except TransientError as error:
            if error.code == "404":
                raise TranscriptionTaskFailed("cloud task expired") from None
            raise
        output = response.json().get("output", {})
        if output.get("task_status") in {"PENDING", "RUNNING"}:
            return None
        results = output.get("results", [])
        if (
            output.get("task_status") != "SUCCEEDED"
            or len(results) != 1
            or results[0].get("subtask_status") != "SUCCEEDED"
        ):
            raise TranscriptionTaskFailed(
                "transcription failed or only partly succeeded; not publishable"
            )
        response = await self._request("GET", results[0]["transcription_url"])
        transcript = response.json()
        duration = (
            transcript.get("properties", {}).get("original_duration_in_milliseconds", 0) / 1000
        )
        if duration <= 0 or abs(duration - expected_duration) > max(3, expected_duration * 0.02):
            raise ValidationFailure("transcription duration does not cover the complete audio")
        parts = transcript.get("transcripts", [])
        text = "\n\n".join(part.get("text", "").strip() for part in parts).strip()
        if not parts or not text or any(not part.get("text", "").strip() for part in parts):
            raise ValidationFailure("transcription is empty or incomplete")
        return {"text": text, "duration": duration, "raw": transcript}


class LocalWhisperClient:
    local = True

    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir
        self.model: WhisperModel | None = None
        self.lock = asyncio.Lock()

    async def upload(self, audio: Path) -> str:
        if not audio.is_file():
            raise ValidationFailure("audio file is unavailable for local transcription")
        return "local:" + str(audio.resolve())

    async def submit(self, audio_url: str) -> str:
        return audio_url

    async def result(self, task_id: str, *, expected_duration: float) -> dict:
        audio = Path(task_id.removeprefix("local:"))
        async with self.lock:
            try:
                return await asyncio.to_thread(self._transcribe, audio, expected_duration)
            except ValidationFailure:
                raise
            except (OSError, RuntimeError) as error:
                raise TransientError(
                    "local transcription failed; saved audio is retained"
                ) from error

    def _transcribe(self, audio: Path, expected_duration: float) -> dict:
        if self.model is None:
            self.model = WhisperModel(str(self.model_dir), device="cuda", compute_type="float16")
        segments, info = self.model.transcribe(str(audio), beam_size=5, vad_filter=False)
        text = "\n\n".join(segment.text.strip() for segment in segments if segment.text.strip())
        duration = float(info.duration)
        if abs(duration - expected_duration) > max(3, expected_duration * 0.02):
            raise ValidationFailure("transcription does not cover the complete audio")
        if not text:
            raise ValidationFailure("local transcription is empty")
        return {
            "text": text,
            "duration": duration,
            "raw": {"engine": "faster-whisper", "language": info.language},
        }
