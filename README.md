# notegen

[![CI](https://github.com/moneytosms/notegen/actions/workflows/ci.yml/badge.svg)](https://github.com/moneytosms/notegen/actions/workflows/ci.yml)

Convert YouTube videos, playlists, and web pages into structured Obsidian-flavored markdown notes using LLMs.

## Install

```bash
pip install notegen
```

## Quick start

```bash
# 1. Create config
notegen config init

# 2. Open config and add your API key
notegen config open

# 3. Verify everything works
notegen doctor

# 4. Generate notes
notegen https://youtube.com/watch?v=...
```

## Usage

```bash
# Auto-detect source type (bare URL or file)
notegen https://youtube.com/watch?v=...
notegen https://youtube.com/playlist?list=...
notegen https://example.com/article
notegen transcript.txt

# Explicit commands
notegen video <youtube-url>
notegen playlist <playlist-url> [--force] [--force-restart]
notegen web <url>
notegen text <file-or-stdin>
notegen text -                          # stdin

# Watch a folder — auto-process new .txt/.md files
notegen watch ./inbox

# Dry run — estimate tokens/cost without calling LLM
notegen -n https://youtube.com/watch?v=...
notegen video <url> --dry-run

# Output format
notegen video <url> --format logseq
notegen web <url> --format plain

# Config
notegen config init      # create config file
notegen config open      # open config in your default editor
notegen config show      # print resolved config
notegen config validate  # check structure + API key presence
notegen doctor           # config check + real test API call

# Cache
notegen cache clear      # remove ~/.cache/notegen/
```

## Options

| Flag | Description |
|---|---|
| `-o / --output-dir PATH` | Override output directory |
| `-m / --model TEXT` | LiteLLM model string (e.g. `groq/llama-3.3-70b-versatile`) |
| `-v / --verbose` | Show chunk count, token usage, model/key selection, crawl status |
| `--no-mermaid` | Disable mermaid diagram generation |
| `--no-cache` | Skip cache read/write for this run |
| `-n / --dry-run` | Print token/cost estimate; skip LLM call |
| `--format TEXT` | Output format: `obsidian` (default) · `logseq` · `plain` · `roam` |
| `--force` | Skip playlist videos without captions instead of aborting |
| `--force-restart` | Ignore playlist resume file, reprocess all videos |

## Config file

### Location

| OS | Path |
|---|---|
| Linux | `~/.config/notes-gen/config.yaml` |
| macOS | `~/.config/notes-gen/config.yaml` |
| Windows | `%USERPROFILE%\.config\notes-gen\config.yaml` |

Run `notegen config init` to generate a fully-commented template, then `notegen config open` to edit it.

### Full reference (`~/.config/notes-gen/config.yaml`)

```yaml
# Active model — format: <provider>/<model-name>
model: anthropic/claude-sonnet-4-6

# Output
output_dir: ~/notes
mermaid: true

# Output format: obsidian (default) | logseq | plain | roam
output_format: obsidian

# Caching — transcripts + LLM output cached in ~/.cache/notegen/
# Set to false to always re-fetch and re-generate
cache: true

# Token budget — compress output if it exceeds this many tokens (0 = no limit)
max_output_tokens: 0

# Fuzzy dedup — skip near-duplicate sections in merged notes (Jaccard threshold)
merger_similarity_threshold: 0.7

# API key rotation — add multiple keys per provider.
# notegen picks one at random each request (useful for free-tier rate limits).
api_keys:
  anthropic:
    - sk-ant-api03-KEY1
    - sk-ant-api03-KEY2   # second key rotated in automatically
  groq:
    - gsk_KEY1
  openai:
    - sk-proj-KEY1
  gemini:
    - AIzaSyKEY1
  nvidia_nim:
    - nvapi-KEY1
  mistral:
    - KEY1
  cohere:
    - KEY1
  together_ai:
    - KEY1
  deepseek:
    - sk-KEY1
  perplexity:
    - pplx-KEY1
  xai:
    - xai-KEY1

# Web crawl limits
max_concurrent: 5
web_max_pages: 50
web_max_depth: 3

# Rate limiting & retry (important for free-tier providers like Groq, Gemini)
max_retries: 5
retry_base_delay: 60.0   # seconds; backoff = base * 2^attempt
```

### Supported providers

| Provider | Model string example |
|---|---|
| Anthropic | `anthropic/claude-sonnet-4-6` |
| OpenAI | `openai/gpt-4o` |
| Groq | `groq/llama-3.3-70b-versatile` |
| Google Gemini | `gemini/gemini-2.0-flash` |
| NVIDIA NIM | `nvidia_nim/meta/llama-3.1-70b-instruct` |
| Mistral | `mistral/mistral-large-latest` |
| Cohere | `cohere/command-r-plus` |
| Together AI | `together_ai/meta-llama/Llama-3-70b-chat-hf` |
| DeepSeek | `deepseek/deepseek-chat` |
| Perplexity | `perplexity/sonar-pro` |
| xAI (Grok) | `xai/grok-2` |
| Ollama (local) | `ollama/llama3` |

Any provider supported by [LiteLLM](https://docs.litellm.ai/docs/providers) works.

## Env var API keys

As an alternative to the config file, set `NOTEGEN_<PROVIDER>_KEY` env vars. These are used as fallback when no keys are configured for a provider:

```bash
export NOTEGEN_GROQ_KEY=gsk_...
export NOTEGEN_ANTHROPIC_KEY=sk-ant-...
export NOTEGEN_GEMINI_KEY=AIzaSy...
```

Config keys take priority over env vars. Env vars are useful for CI or server use.

## Caching

Transcripts and LLM-generated notes are cached in `~/.cache/notegen/` (keyed on URL + model). Re-running the same source skips fetch and LLM calls entirely.

```bash
notegen video <url>          # first run: fetches + generates + caches
notegen video <url>          # second run: serves from cache instantly
notegen video <url> --no-cache   # bypass cache for this run
notegen cache clear          # wipe all cached files
```

## Dry run

Estimate tokens and cost before committing to a run:

```bash
notegen -n https://youtube.com/playlist?list=...
```

Prints a Rich table with chunk count, token count, estimated cost, and estimated generation time. No LLM calls are made, no files are written.

## Output formats

Use `--format` to target different note-taking apps:

| Format | Syntax style |
|---|---|
| `obsidian` (default) | `[[wikilinks]]`, `> [!TIP]` callouts, mermaid diagrams |
| `logseq` | Bullet-based, `#+BEGIN_TIP` blocks |
| `plain` | Clean markdown, no app-specific syntax |
| `roam` | `#[[hashtag refs]]` |

## Watch mode

Drop files into a folder and notegen auto-processes them:

```bash
notegen watch ./inbox --output-dir ./notes
```

- Processes existing unprocessed `.txt`/`.md` files on startup
- Watches for new files; processes each as it appears
- Tracks processed files in `.watch-state.json` (won't reprocess on restart)
- Ctrl+C exits cleanly

## Playlist resume

Long playlists are resumable. Progress is saved to `.progress.json` in the output folder after each video. If a run is interrupted, re-running the same command skips already-completed videos.

```bash
notegen playlist <url>            # resumes from where it left off
notegen playlist <url> --force-restart   # ignore progress, reprocess all
```

## Rate limiting

Free-tier providers (Groq, Gemini, Together AI, etc.) enforce strict TPM/RPM limits. notegen handles 429 errors automatically:

1. Cools down the offending key and rotates to another available key immediately.
2. If all keys for the provider are exhausted, waits using the `Retry-After` header value (if present) or exponential backoff (`retry_base_delay * 2^attempt`), then retries.

With the defaults (`max_retries: 5`, `retry_base_delay: 60`), the wait sequence is 60s → 120s → 240s → 480s → 960s. Adding multiple API keys from different free accounts is the most effective way to stay under limits.

## Output format

Obsidian-flavored markdown (default):
- YAML frontmatter (`title`, `source`, `type`, `tags`, `date`)
- `##` / `###` headings only
- `> [!TIP]` / `> [!WARNING]` callouts
- Mermaid diagrams for flows and architectures
- `[[wikilinks]]` for cross-references
- Tags auto-inferred by LLM from content
- Playlist → folder + `index.md` with wikilinks to each video note

## Requirements

- Python ≥ 3.11
- API key for at least one supported LLM provider
