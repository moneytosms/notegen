import re
import unicodedata
from datetime import date
from typing import Any

import yaml

_MIN_HEADERS_FOR_TOC = 4


def slugify(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = text.strip("-")
    return text


def generate_toc(notes: str) -> str:
    """Insert an Obsidian-compatible TOC after the title heading if >= 4 sections exist."""
    headers = []
    for line in notes.splitlines():
        m = re.match(r"^(#{2,3})\s+(.+)$", line)
        if m:
            indent = "  " * (len(m.group(1)) - 2)
            text = m.group(2).strip()
            headers.append(f"{indent}- [[#{text}|{text}]]")

    if len(headers) < _MIN_HEADERS_FOR_TOC:
        return notes

    toc_block = "## Contents\n\n" + "\n".join(headers)

    title_match = re.search(r"^# .+$", notes, re.MULTILINE)
    if title_match:
        pos = title_match.end()
        return notes[:pos] + "\n\n" + toc_block + "\n" + notes[pos:]

    return toc_block + "\n\n" + notes


def build_frontmatter(
    title: str,
    source: str,
    type: str,
    tags: list[str],
    date: date,
    **kwargs: Any,
) -> str:
    data = {
        "title": title,
        "source": source,
        "type": type,
        "tags": tags,
        "date": date.isoformat(),
    }
    data.update(kwargs)
    return f"---\n{yaml.dump(data, default_flow_style=False, allow_unicode=True)}---\n"
