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

# 3. Generate notes
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
notegen playlist <playlist-url> [--force]
notegen web <url>
notegen text <file-or-stdin>
notegen text -                          # stdin

# Config
notegen config init   # create config file
notegen config open   # open config in your default editor
notegen config show   # print resolved config
```

## Options

| Flag | Description |
|---|---|
| `-o / --output-dir` | Override output directory |
| `-m / --model` | LiteLLM model string (e.g. `groq/llama-3.3-70b-versatile`) |
| `--no-mermaid` | Disable mermaid diagram generation |
| `-v / --verbose` | Show chunk count, token usage, model/key selection, crawl status |
| `--force` | Skip playlist videos without captions instead of aborting |

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
# On a 429 error: cools down the offending key, rotates to another if available,
# otherwise waits using Retry-After header or exponential backoff.
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

## Rate limiting

Free-tier providers (Groq, Gemini, Together AI, etc.) enforce strict TPM/RPM limits. notegen handles 429 errors automatically:

1. Cools down the offending key and rotates to another available key immediately.
2. If all keys for the provider are exhausted, waits using the `Retry-After` header value (if present) or exponential backoff (`retry_base_delay * 2^attempt`), then retries.

With the defaults (`max_retries: 5`, `retry_base_delay: 60`), the wait sequence is 60s → 120s → 240s → 480s → 960s. Adding multiple API keys from different free accounts is the most effective way to stay under limits.

## Output format

Obsidian-flavored markdown:
- YAML frontmatter (`title`, `source`, `type`, `tags`, `date`)
- `##` / `###` headings only
- `> [!TIP]` / `> [!WARNING]` callouts
- Mermaid diagrams for flows and architectures
- `[[wikilinks]]` for cross-references
- Playlist → folder + `index.md` with wikilinks to each video note

## Requirements

- Python ≥ 3.11
- API key for at least one supported LLM provider
