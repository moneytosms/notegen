# Project Suggestions & Improvements

This document tracks potential features and architectural improvements for `notes-gen`.

## 1. Functional Enhancements

- [x] **Custom Prompt Templates**: Allow users to provide their own "style" or "focus" for notes (e.g., "focus on code examples") via named templates in config.
- [x] **Support for Multiple Languages**: Specify target language for transcripts and output (e.g., `--lang es`).
- [x] **Local LLM Support**: Documentation and config examples for Ollama/LM Studio via LiteLLM.
- [x] **Incremental Playlist Updates**: Skip already-processed videos in a playlist to save time/cost.
- [x] **Interactive Mode**: A `notegen interactive` command to build a processing pipeline via prompts.

## 2. Developer Experience (DX)

- [x] **Pydantic for Config**: Use Pydantic for robust validation of `config.yaml`.
- [x] **Structured Logging**: Replace prints with `loguru` or standard `logging` for better debugging.
- [x] **Rich Dashboard**: Use `rich.layout` for a multi-pane status view during large playlist/crawl operations.
- [x] **Type Check Coverage**: Transitioned to **Pyrefly** (Meta) for high-performance type checking.

## 3. Output & Formatting

- [ ] **Callout Theme Customization**: Map content types to specific Obsidian callout tags (e.g., `[!abstract]`).
- [x] **Auto-Generated TOC**: Clickable Table of Contents for long notes (`--toc` flag).
- [x] **Export Formats**: Support PDF/HTML export via `pypandoc`.
- [x] **Better Image Handling**: Detect and embed/download images from web sources.

## 4. Robustness & Reliability

- [x] **Cost Estimation**: Enhanced `--dry-run` showing exact token counts and USD cost per provider.
- [x] **Advanced Retries**: Use `tenacity` for sophisticated backoff/retry on web scraping and API calls.
- [x] **Schema Validation for LLM**: Self-correction nudge for missing `TAGS:` or malformed structure.

## 5. Metadata Enrichment

- [x] **YouTube Chapters**: Use video chapters to inform chunking and headings; inject as context.
- [x] **Web Metadata**: Extract author, publish date, and reading time more reliably.
- [x] **OpenGraph/Twitter Cards**: Use social metadata for better summaries in frontmatter.
