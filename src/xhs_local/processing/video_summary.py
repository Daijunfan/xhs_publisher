"""Lossless paragraph splitting for externally managed video translations."""

import re


def translation_chunks(text: str, limit: int = 6000) -> list[str]:
    """Keep every source character once, preferring paragraph and sentence boundaries."""
    if limit < 1:
        raise ValueError("translation chunk limit must be positive")
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            piece = text[start:end]
            for pattern in (r"\r?\n[ \t]*\r?\n", r"[。！？]\s*|[.!?](?=\s|$)\s*", r"\s+"):
                boundaries = list(re.finditer(pattern, piece))
                if boundaries:
                    end = start + boundaries[-1].end()
                    break
        chunks.append(text[start:end])
        start = end
    return chunks
