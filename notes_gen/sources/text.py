from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from loguru import logger

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
    from notes_gen.output.runner import use_dashboard, log_to_dashboard, update_dashboard_stats
    from notes_gen.processing.chunker import count_tokens
    from notes_gen.processing.dry_run import _cost_str

    title = "stdin-notes" if source == "-" else Path(source).stem.replace("_", " ").replace("-", " ").title()
    
    with use_dashboard(f"Text: {title}", cfg) as db:
        log_to_dashboard(f"Reading source: {source}")
        raw = read_text(source)
        
        log_to_dashboard("Filtering content...")
        filtered = remove_meta(raw)
        
        tokens = count_tokens(filtered)
        update_dashboard_stats(tokens, _cost_str(tokens, cfg.model))
        
        chunks = chunk_text(filtered, max_tokens=12000, overlap=200)

        if cfg.dry_run:
            import typer
            from notes_gen.processing.dry_run import print_dry_run_summary
            print_dry_run_summary(title, source, chunks, cfg.model)
            raise typer.Exit(0)

        cache_key = source if source != "-" else raw[:200]
        if cfg.cache:
            cached_notes = get_notes_cache(cache_key, cfg.model)
        else:
            cached_notes = None

        if cached_notes is not None:
            log_to_dashboard("Using cached notes")
            notes_raw, tags = cached_notes, []
        else:
            log_to_dashboard(f"Generating notes via {cfg.model}...")
            notes_raw, tags = generate_notes(chunks, cfg)
            if cfg.cache:
                set_notes_cache(cache_key, cfg.model, notes_raw)

        log_to_dashboard("Merging and formatting...")
        notes = merge([notes_raw], similarity_threshold=cfg.merger_similarity_threshold)
        if cfg.max_output_tokens > 0:
            notes = compress_notes(notes, cfg.max_output_tokens, cfg)
        notes = format_notes(notes, cfg.output_format)

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
        result_path = write_note(output_path, content)
        log_to_dashboard(f"[green]Completed:[/] {result_path.name}")
        return result_path
