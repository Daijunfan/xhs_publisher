from __future__ import annotations

import asyncio

import pytest

from xhs_local.core.errors import AuthenticationRequired, ValidationFailure
from xhs_local.processing.transcription import ParaformerClient


class Response:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status

    def json(self):
        return self.data


def test_temporary_upload_and_cloud_task_contract_uses_no_plaintext_config_key(tmp_path):
    key = tmp_path / "secret"
    key.write_text("secret-test-value")
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"complete-audio")
    calls = []
    replies = iter(
        [
            Response(
                {
                    "data": {
                        "upload_dir": "temp",
                        "oss_access_key_id": "id",
                        "signature": "sig",
                        "policy": "policy",
                        "x_oss_object_acl": "private",
                        "x_oss_forbid_overwrite": "true",
                        "upload_host": "https://upload.example.test",
                    }
                }
            ),
            Response({}),
            Response({"output": {"task_id": "task"}}),
            Response(
                {
                    "output": {
                        "task_status": "SUCCEEDED",
                        "results": [
                            {
                                "subtask_status": "SUCCEEDED",
                                "transcription_url": "https://result.example.test",
                            }
                        ],
                    }
                }
            ),
            Response(
                {
                    "properties": {"original_duration_in_milliseconds": 60_000},
                    "transcripts": [{"text": "完整转写"}],
                }
            ),
        ]
    )

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return next(replies)

    async def run():
        client = ParaformerClient(key, request=request)
        url = await client.upload(audio)
        assert url.startswith("oss://temp/")
        assert await client.submit(url) == "task"
        assert (await client.result("task", expected_duration=60))["text"] == "完整转写"

    asyncio.run(run())
    assert calls[0][2]["params"]["model"] == "paraformer-v2"
    assert calls[1][2]["data"]["x-oss-object-acl"] == "private"
    assert calls[2][2]["headers"]["X-DashScope-OssResourceResolve"] == "enable"
    assert calls[2][2]["json"]["model"] == "paraformer-v2"
    assert calls[3][0] == "POST"
    assert "headers" not in calls[4][2]  # No key sent to result/object-storage hosts.


@pytest.mark.parametrize(
    "case", ["failed", "partial_subtask", "empty", "short_audio", "missing_duration"]
)
def test_partial_or_failed_cloud_output_is_not_accepted(tmp_path, case):
    key = tmp_path / "key"
    key.write_text("fake")
    output = {
        "task_status": "SUCCEEDED",
        "results": [
            {"subtask_status": "SUCCEEDED", "transcription_url": "https://result.example.test"}
        ],
    }
    transcript = {
        "properties": {"original_duration_in_milliseconds": 60_000},
        "transcripts": [{"text": "完整内容"}],
    }
    if case == "failed":
        output["task_status"] = "FAILED"
    elif case == "partial_subtask":
        output["results"][0]["subtask_status"] = "FAILED"
    elif case == "empty":
        transcript["transcripts"] = []
    elif case == "short_audio":
        transcript["properties"]["original_duration_in_milliseconds"] = 12_000
    else:
        transcript["properties"] = {}
    responses = iter([Response({"output": output}), Response(transcript)])
    client = ParaformerClient(key, request=lambda *_args, **_kwargs: next(responses))
    with pytest.raises(ValidationFailure):
        asyncio.run(client.result("task", expected_duration=60))


def test_pending_and_authentication_failures_never_return_transcription(tmp_path):
    key = tmp_path / "key"
    key.write_text("private-secret")
    client = ParaformerClient(
        key, request=lambda *_args, **_kwargs: Response({"output": {"task_status": "PENDING"}})
    )
    assert asyncio.run(client.result("task", expected_duration=60)) is None
    client.request = lambda *_args, **_kwargs: Response({}, 401)
    with pytest.raises(AuthenticationRequired) as caught:
        asyncio.run(client.result("task", expected_duration=60))
    assert "private-secret" not in str(caught.value)
