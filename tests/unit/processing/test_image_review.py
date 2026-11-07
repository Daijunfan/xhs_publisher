from __future__ import annotations

import asyncio
import base64
import io
import json

import pytest
from PIL import Image

from xhs_local.core.errors import TransientError
from xhs_local.processing.image_review import IMAGE_REVIEW_PROMPT, ImageReviewer
from xhs_local.processing.provider import DeepSeekResponseError


class Provider:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    async def complete(self, messages, *, model):
        self.calls.append((messages, model))
        response = next(self.responses)
        if isinstance(response, BaseException):
            raise response
        return json.dumps(response)


ALLOW = {"approved": True, "reason": "clear"}
REJECT = {"approved": False, "reason": "political"}


@pytest.mark.parametrize(
    "responses,expected,calls",
    [
        ([ALLOW, ALLOW], True, 2),
        ([REJECT], False, 1),
        ([ALLOW, REJECT], False, 2),
    ],
)
def test_images_require_two_independent_approvals(tmp_path, responses, expected, calls):
    path = tmp_path / "picture.png"
    Image.new("RGB", (80, 80), "red").save(path)
    provider = Provider(responses)
    reviewer = ImageReviewer(provider, model="deepseek-flash")
    assert asyncio.run(reviewer((path,))) is expected
    assert len(provider.calls) == calls
    for messages, model in provider.calls:
        assert model == "deepseek-flash"
        assert messages[0]["content"] == IMAGE_REVIEW_PROMPT
        assert [message["role"] for message in messages] == ["system", "user"]
        assert messages[1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    if calls == 2:
        assert provider.calls[0] == provider.calls[1]


def test_gif_later_frames_are_in_both_reviews(tmp_path):
    path = tmp_path / "animation.gif"
    Image.new("RGB", (40, 40), "green").save(
        path,
        save_all=True,
        append_images=[Image.new("RGB", (40, 40), "red")],
        duration=100,
    )
    provider = Provider([ALLOW, REJECT])
    assert not asyncio.run(ImageReviewer(provider, model="deepseek-flash")((path,)))
    for messages, _model in provider.calls:
        blocks = messages[1]["content"][1:]
        assert len(blocks) == 2
        data = base64.b64decode(blocks[-1]["image_url"]["url"].split(",", 1)[1])
        with Image.open(io.BytesIO(data)) as image:
            assert image.getpixel((0, 0)) == (255, 0, 0)


@pytest.mark.parametrize(
    "reply,error",
    [
        (TransientError("offline"), TransientError),
        ({"approved": "true", "reason": "clear"}, DeepSeekResponseError),
        ({"approved": True, "reason": "political"}, DeepSeekResponseError),
    ],
)
def test_failed_or_unreadable_reviews_never_pass(tmp_path, reply, error):
    path = tmp_path / "image.png"
    Image.new("RGB", (40, 40), "white").save(path)
    with pytest.raises(error):
        asyncio.run(ImageReviewer(Provider([reply]), model="deepseek-flash")((path,)))


def test_unreadable_verdict_skips_item(tmp_path):
    path = tmp_path / "image.png"
    Image.new("RGB", (40, 40), "white").save(path)
    reviewer = ImageReviewer(
        Provider([{"approved": False, "reason": "unreadable"}]), model="deepseek-flash"
    )
    assert not asyncio.run(reviewer((path,)))


def test_text_only_items_need_no_vision_request():
    provider = Provider([])
    assert asyncio.run(ImageReviewer(provider, model="deepseek-flash")(()))
    assert provider.calls == []
