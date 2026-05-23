from __future__ import annotations

import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def chunk_text(text: str, max_tokens: int = 12000, overlap: int = 200) -> list[str]:
    if not text.strip():
        return []

    tokens = _ENCODING.encode(text)
    total = len(tokens)

    if total <= max_tokens:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < total:
        end = min(start + max_tokens, total)
        chunk_tokens = tokens[start:end]
        chunks.append(_ENCODING.decode(chunk_tokens))
        if end >= total:
            break
        start = end - overlap

    return chunks
