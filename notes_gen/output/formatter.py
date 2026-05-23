from __future__ import annotations

import re
import unicodedata
from datetime import date

import yaml


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


def build_frontmatter(
    title: str,
    source: str,
    type: str,
    tags: list[str],
    date: date,
) -> str:
    data = {
        "title": title,
        "source": source,
        "type": type,
        "tags": tags,
        "date": date.isoformat(),
    }
    return f"---\n{yaml.dump(data, default_flow_style=False, allow_unicode=True)}---\n"
