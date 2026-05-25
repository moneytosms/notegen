# notegen

Convert YouTube videos, playlists, and web pages into structured, domain-expert-level Obsidian notes using LLMs.

[![Tests](https://github.com/moneytosms/notegen/actions/workflows/ci.yml/badge.svg)](https://github.com/moneytosms/notegen/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-2.4.1-blue)](https://github.com/moneytosms/notegen)

---

## Features

### Notes quality

- **Deep coverage** — Full lecture-style notes with mechanisms, intuitions, worked examples, and gotchas. Not summaries.
- **Rich formatting** — Tables, MathJax, Mermaid diagrams, code blocks, callouts, and wikilinks generated automatically.
- **Obsidian-native** — YAML frontmatter, `[[wikilinks]]`, and `> [!TIP]` callouts out of the box.

### Input sources

- **YouTube videos** — Transcript-based, chapter-aware note structure.
- **YouTube playlists** — Per-video notes with an `index.md` and optional topic subfolders.
- **Web pages** — Same-domain recursive crawl up to configurable depth and page limits.
- **Text files / stdin** — Any plain text or markdown file piped in or passed by path.

### Tooling

- **Interactive mode** — Guided wizard for one-off note generation without memorizing flags.
- **Watch mode** — Monitors a directory and generates notes for every new text file dropped in.
- **Prompt templates** — Named styles (`--template code`, `--template theory`) defined in config.
- **Export** — Generate PDF, HTML, or DOCX alongside the markdown note.
- **Multi-language** — Notes in any language via `--lang` (ISO 639-1 code).

### Reliability

- **Multi-provider** — Any LiteLLM-supported model: Groq, Gemini, Anthropic, OpenAI, Ollama, and more.
- **Key rotation** — Multiple API keys per provider; notegen picks one at random per request.
- **Rate-limit handling** — Exponential backoff with `Retry-After` header awareness via `tenacity`.
- **Caching** — Notes are cached by URL and model; re-runs skip the LLM call unless forced.
- **Rich dashboard** — Real-time progress, token count, and cost estimate per run.

---

## Quick start

### Installation

```bash
# Recommended
uv tool install notegen

# Or via pip
pip install notegen
```

### Setup

Run the interactive setup wizard to configure your provider and API key:

```bash
notegen setup
```

### Basic usage

```bash
# Auto-detect source type (video, playlist, web, or file)
notegen https://www.youtube.com/watch?v=dQw4w9WgXcQ

# Interactive guided mode
notegen interactive

# Crawl a documentation site and export to PDF
notegen web https://docs.python.org/3/ --export pdf

# Process a playlist, skip videos already converted
notegen playlist <playlist_url> --incremental
```

---

## Commands

| Command | Description |
| :------ | :---------- |
| `notegen <url>` | Auto-detect type and generate notes |
| `notegen video <url>` | Single YouTube video |
| `notegen playlist <url>` | Full YouTube playlist |
| `notegen web <url>` | Web page or site crawl |
| `notegen text <file>` | Text file or stdin (`-`) |
| `notegen interactive` | Guided note-generation wizard |
| `notegen watch <dir>` | Watch directory for new files |
| `notegen setup` | Interactive first-run configuration |
| `notegen doctor` | Check environment and LLM connectivity |
| `notegen config init` | Create default config file |
| `notegen config open` | Open config in system editor |
| `notegen config show` | Print current settings (keys masked) |
| `notegen config validate` | Validate config and report errors |
| `notegen cache clear` | Delete all local cache entries |

### Common flags

These flags apply to `video`, `playlist`, `web`, `text`, and `auto`:

| Flag | Description |
| :--- | :---------- |
| `-o, --output-dir <path>` | Override output directory |
| `-m, --model <str>` | Override LLM model string |
| `-n, --dry-run` | Estimate cost, skip LLM calls |
| `-v, --verbose` | Show detailed logs |
| `--lang <code>` | Target language (e.g. `en`, `es`, `hi`) |
| `-t, --template <name>` | Apply named prompt style from config |
| `--export <fmt>` | Export to `pdf`, `html`, or `docx` |
| `--toc` | Insert a table of contents after the title |
| `--no-cache` | Skip cache read and write |
| `--no-mermaid` | Omit Mermaid diagram instructions |
| `--incremental` | Skip files that already exist (playlist) |

---

## Configuration

Config file location:

- **Linux / macOS** — `~/.config/notes-gen/config.yaml`
- **Windows** — `%USERPROFILE%\.config\notes-gen\config.yaml`

Run `notegen config init` to create a default file, or `notegen setup` for guided configuration.

### Key options

```yaml
# LiteLLM model string — provider/model-name
model: groq/llama-3.3-70b-versatile

# Where notes are written
output_dir: ~/notes

# Multiple keys per provider for rate-limit rotation
api_keys:
  groq:
    - gsk_XXXX
    - gsk_YYYY
  anthropic:
    - sk-ant-api03-XXXX

# Web crawl limits
web_max_pages: 50
web_max_depth: 3

# Retry behaviour for rate-limited providers
max_retries: 5
retry_base_delay: 60.0

# Named prompt styles
prompt_templates:
  code: "Focus on implementation details and syntax. Minimize theoretical fluff."
  theory: "Focus on high-level architecture and design patterns. Keep code brief."
```

Use a template:

```bash
notegen video <url> --template code
```

### Environment variable fallback

If no key is set in config for a provider, notegen checks:

```
NOTEGEN_<PROVIDER>_KEY   (e.g. NOTEGEN_GROQ_KEY, NOTEGEN_ANTHROPIC_KEY)
```

### Supported providers (free tier available)

| Provider | Free tier | Notes |
| :------- | :-------- | :---- |
| `groq` | Yes | Fast inference; recommended default |
| `nvidia_nim` | Yes | build.nvidia.com |
| `gemini` | Yes | Google AI Studio |
| `anthropic` | No | Paid |
| `openai` | No | Paid |
| `ollama` | Local | No key needed |

Any [LiteLLM-supported provider](https://docs.litellm.ai/docs/providers) works with the right model string.

---

## Note format

Notes are Obsidian-flavored markdown with:

- **YAML frontmatter** — title, source, tags, date
- **Wikilinks** — `[[Concept]]` on first mention of notable terms
- **Callouts** — `> [!TIP]`, `> [!WARNING]`, `> [!EXAMPLE]`, etc.
- **Mermaid diagrams** — for flows, architectures, and state machines
- **Tables** — for comparisons; pipes on every row, explicit alignment
- **Math** — `$inline$` and `$$block$$` for formulas

---

## Development

```bash
# Install dependencies
uv sync --dev

# Run tests
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .

# Type check
uv run pyrefly check
```

Tests are unit-only — no network calls, no LLM. All external calls are mocked.

---

## License

MIT
