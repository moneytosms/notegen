from __future__ import annotations

import re

_HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
_MIN_WORDS_FOR_SIMILARITY = 50


def _jaccard_similarity(a: str, b: str) -> float:
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def merge(notes: list[str], similarity_threshold: float = 0.7) -> str:
    if not notes:
        return ""

    seen_headers: set[str] = set()
    seen_bodies: list[str] = []
    output_sections: list[tuple[str, str]] = []

    for note in notes:
        if not note.strip():
            continue
        sections = _split_into_sections(note)
        for header, body in sections:
            key = header.strip().lower() if header else None
            if key and key in seen_headers:
                continue

            body_words = len(body.split())
            if body_words >= _MIN_WORDS_FOR_SIMILARITY:
                if any(
                    _jaccard_similarity(body, existing) >= similarity_threshold
                    for existing in seen_bodies
                ):
                    continue

            if key:
                seen_headers.add(key)
            if body_words >= _MIN_WORDS_FOR_SIMILARITY:
                seen_bodies.append(body)
            output_sections.append((header, body))

    if not output_sections:
        return ""

    parts: list[str] = []
    for header, body in output_sections:
        if header:
            parts.append(f"{header}\n\n{body.strip()}")
        else:
            parts.append(body.strip())

    return "\n\n".join(p for p in parts if p)


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split text into (header, body) pairs. First section may have no header."""
    positions = [(m.start(), m.group()) for m in _HEADER_RE.finditer(text)]
    if not positions:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    if positions[0][0] > 0:
        sections.append(("", text[: positions[0][0]]))

    for i, (pos, header) in enumerate(positions):
        header_end = pos + len(header)
        next_pos = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        body = text[header_end:next_pos].lstrip("\n")
        sections.append((header, body))

    return sections
