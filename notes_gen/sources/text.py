from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from notes_gen.config import Config
from notes_gen.output.formats import format_notes
from notes_gen.output.formatter import build_frontmatter, slugify
from notes_gen.output.writer import write_note
from notes_gen.processing.chunker import chunk_text
from notes_gen.processing.filter import remove_meta
from notes_gen.processing.llm import compress_notes, generate_notes
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
    from notes_gen.cache import get_notes_cache, set_notes_cache

    raw = read_text(source)
    cache_key = source if source != "-" else raw[:200]
    filtered = remove_meta(raw)
    chunks = chunk_text(filtered, max_tokens=12000, overlap=200)

    if cfg.dry_run:
        import typer

        from notes_gen.processing.dry_run import print_dry_run_summary

        title_for_dry = (
            "stdin-notes"
            if source == "-"
            else Path(source).stem.replace("_", " ").replace("-", " ").title()
        )
        print_dry_run_summary(title_for_dry, source, chunks, cfg.model)
        raise typer.Exit(0)

    if cfg.cache:
        cached_notes = get_notes_cache(cache_key, cfg.model)
    else:
        cached_notes = None

    if cached_notes is not None:
        notes_raw, tags = cached_notes, []
    else:
        notes_raw, tags = generate_notes(chunks, cfg)
        if cfg.cache:
            set_notes_cache(cache_key, cfg.model, notes_raw)

    notes = merge([notes_raw], similarity_threshold=cfg.merger_similarity_threshold)
    if cfg.max_output_tokens > 0:
        notes = compress_notes(notes, cfg.max_output_tokens, cfg)
    notes = format_notes(notes, cfg.output_format)

    if source == "-":
        title = "stdin-notes"
    else:
        title = Path(source).stem.replace("_", " ").replace("-", " ").title()

    slug = slugify(title) or "notes"
    frontmatter = build_frontmatter(
        title=title,
        source=source if source != "-" else "stdin",
        type="article",
        tags=tags,
        date=date.today(),
    )
    content = frontmatter + "\n" + notes

    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = cfg.output_dir / f"{slug}.md"
    return write_note(output_path, content)
