from __future__ import annotations

import re

_HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def merge(notes: list[str]) -> str:
    if not notes:
        return ""

    seen_headers: set[str] = set()
    output_sections: list[str] = []

    for note in notes:
        if not note.strip():
            continue
        sections = _split_into_sections(note)
        for header, body in sections:
            key = header.strip().lower() if header else None
            if key and key in seen_headers:
                continue
            if key:
                seen_headers.add(key)
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
