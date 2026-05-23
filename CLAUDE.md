# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package Manager

**Use `uv` exclusively.** Never use `pip`, `pip install`, `python -m pip`, or `venv` directly.

```bash
uv sync                        # install all dependencies
uv add <package>               # add dependency
uv add --dev <package>         # add dev dependency
uv run notes-gen <args>        # run CLI entry point
uv run pytest                  # run tests
uv run pytest tests/test_chunker.py::test_name  # single test
uv run ruff check .            # lint
uv run ruff format .           # format
```

## Documentation

When implementing or debugging any library used in this project (`litellm`, `typer`, `trafilatura`, `youtube-transcript-api`, `yt-dlp`, `httpx`, `tiktoken`, `rich`, etc.), **always use the context7 MCP server** to fetch current docs before writing code. Do not rely on training data for library APIs.

```
mcp__plugin_context7_context7__resolve-library-id  →  then  mcp__plugin_context7_context7__query-docs
```

## Architecture

See `SPEC.md` for full product spec. High-level data flow:

```
CLI (cli.py)
  → sources/ (fetch raw content)
      youtube.py   — transcript via youtube-transcript-api, metadata via yt-dlp
      web.py       — crawl + extract via trafilatura/httpx (same-domain, max depth 3, max 50 pages)
      text.py      — stdin or file passthrough
  → processing/ (transform content)
      filter.py    — strip meta-commentary before LLM call
      chunker.py   — token-aware splitting (~12k tokens, 200-token overlap, tiktoken)
      llm.py       — litellm wrapper; prompt templates; tag auto-inference
      merger.py    — merge per-chunk notes, deduplicate
  → output/ (write files)
      formatter.py — slugify titles, build YAML frontmatter, wikilinks
      writer.py    — create dirs, write .md files, build index.md for playlists
```

Config flows: `config.py` loads `~/.config/notes-gen/config.yaml`, merges CLI flag overrides, passes resolved `Config` dataclass through the entire pipeline.

## Key Behaviors

- **No captions on YouTube video** → fail loudly (print video title + URL), skip in playlist unless `--force`
- **Playlist output** → `<playlist-name>/index.md` with `[[wikilinks]]` to per-video files; topic subfolders only if ≥3 videos clearly cluster
- **Web crawl** → same-domain internal links only, dedup URLs, respects `web_max_pages` / `web_max_depth` config
- **LLM** → all calls via `litellm`; model string from config (e.g. `anthropic/claude-sonnet-4-6`); API keys from env vars only
- **Completeness over brevity** — never truncate notes to fit a size limit

## Note Format

Obsidian-flavored markdown: YAML frontmatter, `> [!TIP]` / `> [!WARNING]` callouts, `[[wikilinks]]`, mermaid diagrams for flows/architectures. Tags auto-inferred by LLM from content.

## Testing

- Unit tests: no network, no LLM — mock `youtube-transcript-api`, `httpx`, `litellm`
- Fixtures live in `tests/fixtures/`
- Coverage target: 80% on `processing/` and `output/`
