# Project Suggestions & Improvements

This document tracks potential features and architectural improvements for `notes-gen`.

## 1. Functional Enhancements

- [ ] **Custom Prompt Templates**: Allow users to provide their own "style" or "focus" for notes (e.g., "focus on code examples").
- [ ] **Support for Multiple Languages**: Specify target language for transcripts and output (e.g., `--lang es`).
- [ ] **Local LLM Support**: Documentation and config examples for Ollama/LM Studio via LiteLLM.
- [ ] **Incremental Playlist Updates**: Skip already-processed videos in a playlist to save time/cost.
- [ ] **Interactive Mode**: A `notegen interactive` command to build a processing pipeline via prompts.

## 2. Developer Experience (DX)

- [ ] **Pydantic for Config**: Use Pydantic for robust validation of `config.yaml`.
- [ ] **Structured Logging**: Replace prints with `loguru` or standard `logging` for better debugging.
- [ ] **Rich Dashboard**: Use `rich.layout` for a multi-pane status view during large playlist/crawl operations.
- [ ] **Type Check Coverage**: Ensure `mypy` or `pyright` passes across the entire codebase.

## 3. Output & Formatting

- [ ] **Callout Theme Customization**: Map content types to specific Obsidian callout tags (e.g., `[!abstract]`).
- [ ] **Auto-Generated TOC**: Clickable Table of Contents for long notes.
- [ ] **Export Formats**: Support PDF/HTML export via `pandoc` or `markdown-it-py`.
- [ ] **Better Image Handling**: Detect and embed/download images from web sources.

## 4. Robustness & Reliability

- [ ] **Cost Estimation**: Enhanced `--dry-run` showing exact token counts and USD cost per provider.
- [ ] **Advanced Retries**: Use `tenacity` for sophisticated backoff/retry on web scraping and API calls.
- [ ] **Schema Validation for LLM**: Use instructor or JSON mode to ensure `TAGS:` and structure are always perfect.

## 5. Metadata Enrichment

- [ ] **YouTube Chapters**: Use video chapters (if available) to inform chunking and headings.
- [ ] **Web Metadata**: Extract author, publish date, and reading time more reliably.
- [ ] **OpenGraph/Twitter Cards**: Use social metadata for better summaries in frontmatter.
