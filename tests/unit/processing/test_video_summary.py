from __future__ import annotations

import pytest

from xhs_local.processing.video_summary import (
    translation_chunks,
)


@pytest.mark.parametrize("limit", [1, 2, 7, 18, 6000])
@pytest.mark.parametrize(
    "text",
    [
        "",
        " \n\t ",
        "第一段。\n\nSecond paragraph!  More facts?\r\n\r\n数字 3.14 与公式 x² + y²。🙂末尾",
        "unbroken-source" * 1000,
        "甲。乙！丙？\n\n" * 1200 + "FINAL_FACT",
    ],
)
def test_translation_chunks_preserve_exact_source_once_in_order(text, limit):
    chunks = translation_chunks(text, limit)
    assert "".join(chunks) == text
    assert all(0 < len(chunk) <= limit for chunk in chunks)
    assert chunks == translation_chunks(text, limit)


def test_translation_chunks_prefer_paragraph_then_sentence_boundaries():
    assert translation_chunks("First paragraph.\n\nNext sentence. Rest.", 34)[0] == (
        "First paragraph.\n\n"
    )
    assert translation_chunks("First thought. Second sentence continues.", 25)[0] == (
        "First thought. "
    )
    assert translation_chunks("第一句完整。第二句仍然继续且很长", 12)[0] == "第一句完整。"
    with pytest.raises(ValueError, match="positive"):
        translation_chunks("text", 0)
