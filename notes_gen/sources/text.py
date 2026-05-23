from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from notes_gen.config import Config
from notes_gen.output.formatter import build_frontmatter, slugify
from notes_gen.output.writer import write_note
from notes_gen.processing.chunker import chunk_text
from notes_gen.processing.filter import remove_meta
from notes_gen.processing.llm import generate_notes
from notes_gen.processing.merger import merge


def read_text(source: str) -> str:
    if source == "-":
        raw = sys.stdin.read()
    else:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {source}")
        raw = path.read_text(encoding="utf-8")
    return _normalize(raw)


def _normalize(text: str) -> str:
    text = re.sub(r"\t", " ", text)
    text = re.sub(r" {3,}", " ", text)
    return text.strip()


def run_text_pipeline(source: str, cfg: Config) -> Path:
    raw = read_text(source)
    filtered = remove_meta(raw)
    chunks = chunk_text(filtered, max_tokens=12000, overlap=200)
    chunk_notes = generate_notes(chunks, cfg)
    notes = merge([chunk_notes]) if isinstance(chunk_notes, str) else merge(chunk_notes)

    if source == "-":
        title = "stdin-notes"
    else:
        title = Path(source).stem.replace("_", " ").replace("-", " ").title()

    slug = slugify(title) or "notes"
    frontmatter = build_frontmatter(
        title=title,
        source=source if source != "-" else "stdin",
        type="article",
        tags=[],
        date=date.today(),
    )
    content = frontmatter + "\n" + notes

    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = cfg.output_dir / f"{slug}.md"
    return write_note(output_path, content)
