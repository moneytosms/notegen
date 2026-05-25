# notegen 🚀

Convert YouTube videos, playlists, and web pages into beautifully formatted, domain-expert level Obsidian notes using LLMs.

[![Tests](https://github.com/moneytosms/notegen/actions/workflows/ci.yml/badge.svg)](https://github.com/moneytosms/notegen/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-2.4.0-blue)](https://github.com/moneytosms/notegen)

---

## ✨ Key Features

### 🧠 Domain-Expert Notes
*   **Deep Dives**: Not just summaries—full lecture notes with mechanisms, intuitions, and worked examples.
*   **Rich Formatting**: Automatic tables, MathJax ($x^2$), Mermaid diagrams, and code blocks.
*   **Obsidian Ready**: Full support for [[Wikilinks]], callouts (`> [!TIP]`), and YAML frontmatter.

### 🎥 Multimedia & Web Power
*   **YouTube Chapters**: Automatically uses video chapters to inform note structure.
*   **Smart Web Crawl**: Recursively crawls documentation or articles, extracting clean content while skipping nav/footers.
*   **Image Handling**: Automatically extracts and downloads primary images to a local `assets/` folder.

### 🛠️ Advanced Tooling
*   **Interactive Mode**: A guided wizard to build your note-generation pipeline (`notegen interactive`).
*   **Prompt Templates**: Reusable styles (e.g., `--template code` vs `--template theory`) defined in your config.
*   **Multi-Language**: Support for 50+ languages via YouTube translation and LLM output directives.
*   **Export Formats**: Generate **PDF**, **HTML**, or **DOCX** versions of your notes on the fly.
*   **Rich Dashboard**: Real-time progress dashboard with token tracking and cost estimation.

### 🛡️ Reliability & Speed
*   **Local LLM Support**: Use Ollama or LM Studio via LiteLLM for private, free note generation.
*   **Advanced Retries**: Automatic exponential backoff and rate-limit rotation using `tenacity`.
*   **Pydantic Config**: Robust validation of your `config.yaml`.
*   **Lightning Fast**: Powered by `uv`, `loguru`, and `anyio` for high-concurrency operations.

---

## 🚀 Quick Start

### 1. Installation
```bash
# Install via uv (recommended)
uv tool install notegen

# Or via pip
pip install notegen
```

### 2. Setup
Run the interactive setup wizard to configure your LLM provider (Groq, Anthropic, Gemini, OpenAI, etc.):
```bash
notegen setup
```

### 3. Usage
```bash
# Auto-detect and generate (Video, Web, or File)
notegen https://www.youtube.com/watch?v=dQw4w9WgXcQ

# Launch the interactive wizard
notegen interactive

# Crawl a documentation site and export to PDF
notegen web https://docs.python.org/3/ --export pdf

# Process a playlist skipping already-done videos
notegen playlist <playlist_url> --incremental
```

---

## ⚙️ Configuration

Your config lives at `~/.config/notes-gen/config.yaml`. You can define custom templates there:

```yaml
prompt_templates:
  code: "Focus heavily on implementation details and syntax."
  theory: "Focus on high-level architecture and design patterns."
```

Use them via:
```bash
notegen video <url> --template code
```

---

## 📊 Dashboard

The **Rich Dashboard** provides a real-time view of your processing pipeline:
- **Activity Log**: Every step from fetching to merging.
- **Progress Bars**: Overall status for playlists or crawls.
- **Live Stats**: Cumulative tokens processed and estimated USD cost.

---

## 🧪 Development & Type Safety

`notegen` is built with modern engineering standards:
- **Type Checking**: Verified with **Pyrefly** (Meta).
- **Logging**: High-performance structured logs with **Loguru**.
- **Testing**: Comprehensive suite with 150+ tests.

```bash
# Run type check
uv run pyrefly check

# Run tests
uv run pytest
```

---

## 📄 License
MIT
