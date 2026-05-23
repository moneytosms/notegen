# Implementation Plan: notes-gen

## Overview

CLI tool converting YouTube videos/playlists and web pages into complete Obsidian-style markdown notes. Built in Python with `uv`, using `litellm` for provider-agnostic LLM calls, `typer` for CLI, and `trafilatura`/`youtube-transcript-api` for content extraction.

## Architecture Decisions

- **Config flows explicitly**: `Config` dataclass instantiated in `cli.py`, passed as argument — no global state or singletons.
- **Processing is sync-first**: `chunker`, `filter`, `merger`, `formatter` are pure sync functions. Async only at fetch boundaries (`sources/`).
- **Vertical slices**: each phase delivers a runnable `uv run notes-gen` command, not just library code.
- **Tests mock at the boundary**: `youtube-transcript-api`, `httpx`, and `litellm` calls are mocked — no network in tests ever.

## Dependency Graph

```
pyproject.toml
    └── notes_gen/config.py (Config dataclass)
            │
            ├── notes_gen/sources/text.py
            ├── notes_gen/sources/youtube.py  (youtube-transcript-api, yt-dlp)
            └── notes_gen/sources/web.py      (httpx, trafilatura, bs4)
                    │
                    └── notes_gen/processing/filter.py
                            │
                            └── notes_gen/processing/chunker.py  (tiktoken)
                                    │
                                    └── notes_gen/processing/llm.py  (litellm)
                                            │
                                            └── notes_gen/processing/merger.py
                                                    │
                                                    └── notes_gen/output/formatter.py
                                                            │
                                                            └── notes_gen/output/writer.py
                                                                    │
                                                                    └── notes_gen/cli.py (typer)
```

---

## Phase 1: Foundation

### Task 1: Project scaffold

**Description:** Initialize the uv project, directory structure, all `__init__.py` files, `pyproject.toml` with all dependencies, and `ruff` config. No logic yet — just a working installable package that can be invoked with `uv run notes-gen`.

**Acceptance criteria:**
- [ ] `uv sync` completes without errors
- [ ] `uv run notes-gen --help` prints help text (even if commands are stubs)
- [ ] `uv run ruff check .` passes with zero errors
- [ ] All directories from SPEC.md §8 exist with `__init__.py`

**Verification:**
- [ ] `uv sync && uv run notes-gen --help`
- [ ] `uv run ruff check .`

**Dependencies:** None

**Files:**
- `pyproject.toml`
- `notes_gen/__init__.py`
- `notes_gen/cli.py` (stub typer app)
- `notes_gen/sources/__init__.py`
- `notes_gen/processing/__init__.py`
- `notes_gen/output/__init__.py`
- `tests/__init__.py`
- `tests/fixtures/` (empty dir)

**Scope:** S

---

### Task 2: Config system

**Description:** Implement `config.py` — the `Config` dataclass, YAML load from `~/.config/notes-gen/config.yaml`, and CLI flag merge logic. Also implement `notes-gen config init` and `notes-gen config show` commands.

**Acceptance criteria:**
- [ ] `Config` dataclass has all fields from SPEC.md §7
- [ ] Missing config file → uses defaults (no error)
- [ ] CLI flags override config file values
- [ ] `notes-gen config init` writes default config to `~/.config/notes-gen/config.yaml` (won't overwrite existing)
- [ ] `notes-gen config show` prints resolved config as YAML

**Verification:**
- [ ] `uv run pytest tests/test_config.py -v`
- [ ] `uv run notes-gen config init && uv run notes-gen config show`

**Dependencies:** Task 1

**Files:**
- `notes_gen/config.py`
- `notes_gen/cli.py` (config subcommands)
- `tests/test_config.py`

**Scope:** S

---

### Task 3: Core processing pipeline

**Description:** Implement `filter.py`, `chunker.py`, `llm.py`, and `merger.py`. This is the transformation heart of the tool — pure functions where possible, fully testable without network.

- `filter.py`: regex + heuristic removal of meta-commentary patterns
- `chunker.py`: split text into ~12k token chunks with 200-token overlap, using `tiktoken`
- `llm.py`: `litellm.completion()` wrapper with system prompt template; returns notes string per chunk; auto-infers tags
- `merger.py`: concatenate chunk notes, deduplicate repeated headers/concepts

**Acceptance criteria:**
- [ ] `chunker.chunk_text("...", max_tokens=12000, overlap=200)` returns correct list of strings
- [ ] Chunks respect token limits (verified with tiktoken)
- [ ] `filter.remove_meta(text)` strips sponsor/subscribe patterns, keeps conceptual content
- [ ] `llm.generate_notes(chunks, config)` calls `litellm.completion` with correct model + prompt
- [ ] `merger.merge(notes_list)` deduplicates sections with identical headers
- [ ] All tests pass with mocked litellm

**Verification:**
- [ ] `uv run pytest tests/test_chunker.py tests/test_filter.py tests/test_llm.py tests/test_merger.py -v`
- [ ] `uv run ruff check notes_gen/processing/`

**Dependencies:** Task 2

**Files:**
- `notes_gen/processing/filter.py`
- `notes_gen/processing/chunker.py`
- `notes_gen/processing/llm.py`
- `notes_gen/processing/merger.py`
- `tests/test_chunker.py`
- `tests/test_filter.py`
- `tests/test_llm.py`
- `tests/test_merger.py`

**Scope:** M

---

### Task 4: Output system

**Description:** Implement `formatter.py` and `writer.py`. Formatter handles slug generation, YAML frontmatter construction, and wikilink formatting. Writer handles directory creation, file writing with overwrite prompts, and `index.md` generation for playlists.

**Acceptance criteria:**
- [ ] `formatter.slugify("FastAPI Tutorial #1!")` → `"fastapi-tutorial-1"`
- [ ] `formatter.build_frontmatter(title, source, type, tags, date)` produces valid YAML block
- [ ] `writer.write_note(path, content, overwrite_policy)` prompts on conflict (overwrite/skip/rename)
- [ ] `writer.write_index(playlist_dir, video_slugs)` writes `index.md` with `[[wikilinks]]`

**Verification:**
- [ ] `uv run pytest tests/test_formatter.py tests/test_writer.py -v`

**Dependencies:** Task 2

**Files:**
- `notes_gen/output/formatter.py`
- `notes_gen/output/writer.py`
- `tests/test_formatter.py`
- `tests/test_writer.py`

**Scope:** S

---

## Checkpoint: Phase 1

- [ ] `uv sync` clean
- [ ] `uv run pytest` — all tests pass
- [ ] `uv run ruff check .` — zero errors
- [ ] `uv run notes-gen config init && notes-gen config show` works
- [ ] **Human review before Phase 2**

---

## Phase 2: Text Pipeline (First Working Vertical Slice)

### Task 5: Text input → notes file

**Description:** Implement `sources/text.py` and wire `notes-gen text <file|->` end-to-end. After this task, the tool works for pasted transcripts: `echo "my notes content" | uv run notes-gen text -`.

**Acceptance criteria:**
- [ ] `notes-gen text transcript.txt` reads file, runs pipeline, writes `<output_dir>/transcript.md`
- [ ] `cat transcript.txt | notes-gen text -` works via stdin
- [ ] Output file has valid YAML frontmatter with auto-inferred tags
- [ ] `type: article` in frontmatter for text input
- [ ] Fails clearly if file not found

**Verification:**
- [ ] `uv run pytest tests/test_text.py -v`
- [ ] Manual: `echo "FastAPI is a modern Python web framework..." | uv run notes-gen text - --output-dir /tmp/test-notes && cat /tmp/test-notes/*.md`

**Dependencies:** Tasks 3, 4

**Files:**
- `notes_gen/sources/text.py`
- `notes_gen/cli.py` (text command wired)
- `tests/test_text.py`
- `tests/fixtures/sample_transcript.txt`

**Scope:** S

---

## Checkpoint: Phase 2

- [ ] `uv run pytest` — all tests pass
- [ ] End-to-end text → notes works with real LLM call (manual smoke test)
- [ ] Output file opens correctly in Obsidian (manual check)
- [ ] **Human review before Phase 3**

---

## Phase 3: YouTube

### Task 6: YouTube single video

**Description:** Implement `sources/youtube.py` for single video fetching and wire `notes-gen video <url>`. Includes transcript fetch with fallback, metadata extraction, and loud failure when no captions exist.

**Acceptance criteria:**
- [ ] Fetches transcript via `youtube-transcript-api` by default
- [ ] Falls back to `yt-dlp --write-auto-sub` if API returns empty
- [ ] Extracts title, channel, URL into `VideoMetadata` dataclass
- [ ] If no captions at all: prints `ERROR: No captions for "<title>" (<url>)` and exits non-zero
- [ ] `notes-gen video <url>` writes `<slugified-title>.md` to output dir
- [ ] `type: video` in frontmatter

**Verification:**
- [ ] `uv run pytest tests/test_youtube.py -v`
- [ ] Manual: `uv run notes-gen video https://youtube.com/watch?v=<known-id>`

**Dependencies:** Tasks 3, 4, 5

**Files:**
- `notes_gen/sources/youtube.py`
- `notes_gen/cli.py` (video command)
- `tests/test_youtube.py`

**Scope:** M

---

### Task 7: YouTube playlist

**Description:** Extend `sources/youtube.py` and implement `notes-gen playlist <url>`. Enumerates playlist with `yt-dlp`, fetches all transcripts in parallel (max 5 concurrent), handles per-video errors with `--force`, detects topic clusters, and writes playlist folder with `index.md`.

**Acceptance criteria:**
- [ ] Enumerates all videos in playlist via `yt-dlp`
- [ ] Fetches transcripts in parallel, max `config.max_concurrent` workers
- [ ] No-caption video: prints error, skips; continues if `--force`, aborts otherwise
- [ ] Writes `<playlist-name>/index.md` with `[[wikilinks]]` to each video note
- [ ] Topic grouping: if LLM detects ≥3 videos sharing distinct theme, creates subfolder (asks user to confirm)
- [ ] Rich progress bar shows video-by-video progress

**Verification:**
- [ ] `uv run pytest tests/test_youtube.py -v` (playlist tests)
- [ ] Manual: `uv run notes-gen playlist <playlist-url>`

**Dependencies:** Task 6

**Files:**
- `notes_gen/sources/youtube.py` (playlist functions)
- `notes_gen/cli.py` (playlist command)
- `notes_gen/output/writer.py` (index.md logic)
- `tests/test_youtube.py`

**Scope:** M

---

## Checkpoint: Phase 3

- [ ] `uv run pytest` — all tests pass
- [ ] Manual: single video produces correct Obsidian note
- [ ] Manual: playlist produces folder + index.md with working wikilinks
- [ ] **Human review before Phase 4**

---

## Phase 4: Web

### Task 8: Web single page

**Description:** Implement `sources/web.py` for single URL fetching and wire `notes-gen web <url>`. Uses `trafilatura` for content extraction with `beautifulsoup4` fallback.

**Acceptance criteria:**
- [ ] Fetches page with `httpx`, sets a browser-like user-agent
- [ ] Extracts main content via `trafilatura`; falls back to bs4 if trafilatura returns empty
- [ ] Strips nav, ads, footers from extracted content
- [ ] `notes-gen web <url>` writes `<slugified-title>.md`
- [ ] `type: article` in frontmatter with source URL

**Verification:**
- [ ] `uv run pytest tests/test_web.py -v` (mocked httpx)
- [ ] Manual: `uv run notes-gen web https://docs.python.org/3/library/asyncio.html`

**Dependencies:** Tasks 3, 4

**Files:**
- `notes_gen/sources/web.py`
- `notes_gen/cli.py` (web command)
- `tests/test_web.py`
- `tests/fixtures/sample_html.html`

**Scope:** M

---

### Task 9: Web crawl (follow internal links)

**Description:** Extend `sources/web.py` to crawl same-domain internal links up to `web_max_depth` levels and `web_max_pages` pages. Produces one combined notes file per crawled site, or multiple files if content is extensive.

**Acceptance criteria:**
- [ ] Discovers internal links from extracted content
- [ ] Skips external domains, deduplicates visited URLs
- [ ] Respects `web_max_pages` (default 50) and `web_max_depth` (default 3)
- [ ] Progress shown via rich (page N of max)
- [ ] If single-page content → single `.md`; if multi-page → folder with `index.md` + per-page notes

**Verification:**
- [ ] `uv run pytest tests/test_web.py -v` (crawl tests with mocked responses)
- [ ] Manual: `uv run notes-gen web https://fastapi.tiangolo.com/tutorial/`

**Dependencies:** Task 8

**Files:**
- `notes_gen/sources/web.py` (crawl logic)
- `notes_gen/output/writer.py` (multi-page output)
- `tests/test_web.py`

**Scope:** M

---

## Checkpoint: Phase 4

- [ ] `uv run pytest` — all tests pass
- [ ] Manual: web single page works
- [ ] Manual: crawl follows links, respects depth/page limits
- [ ] **Human review before Phase 5**

---

## Phase 5: Polish

### Task 10: Auto-detect source + rich progress

**Description:** Wire `notes-gen <source>` auto-detection (YouTube video URL, playlist URL, or web URL). Add rich progress bars to all long-running operations.

**Acceptance criteria:**
- [ ] `notes-gen https://youtube.com/watch?v=...` → runs video command
- [ ] `notes-gen https://youtube.com/playlist?list=...` → runs playlist command
- [ ] `notes-gen https://example.com` → runs web command
- [ ] Playlist: rich progress bar per video
- [ ] Web crawl: rich progress bar per page
- [ ] `--verbose` flag shows per-chunk LLM call progress

**Verification:**
- [ ] `uv run pytest tests/test_cli.py -v`
- [ ] Manual: bare URL auto-routes correctly

**Dependencies:** Tasks 6, 7, 9

**Files:**
- `notes_gen/cli.py` (auto-detect command)
- `tests/test_cli.py`

**Scope:** S

---

## Final Checkpoint

- [ ] `uv run pytest` — all tests pass, ≥80% coverage on `processing/` and `output/`
- [ ] `uv run ruff check .` — zero errors
- [ ] `uv run ruff format --check .` — no format diffs
- [ ] Manual smoke test: video, playlist, web, text all produce valid Obsidian notes
- [ ] Notes open correctly in Obsidian: frontmatter renders, wikilinks resolve, callouts display, mermaid renders

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `youtube-transcript-api` rate-limited or blocked | High | Implement yt-dlp fallback in Task 6; loud error message |
| `trafilatura` returns empty for JS-heavy pages | Medium | bs4 fallback in Task 8; warn user if fallback used |
| LLM context limits on very long playlists | Medium | Chunker + merger in Task 3 handles this by design |
| Topic grouping LLM call adds latency for large playlists | Low | Make it optional; only trigger if user accepts prompt |
| `litellm` model string format differences across providers | Medium | Document in CLAUDE.md; test with multiple providers manually |

## Open Questions

- None — all resolved in spec + user clarifications.
