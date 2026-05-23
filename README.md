# notegen

Convert YouTube videos, playlists, and web pages into structured Obsidian-flavored markdown notes using LLMs.

## Install

```bash
pip install notegen
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
notegen config init   # create ~/.config/notes-gen/config.yaml
notegen config show   # print resolved config
```

## Options

| Flag | Description |
|---|---|
| `-o / --output-dir` | Override output directory |
| `-m / --model` | LiteLLM model string (e.g. `groq/llama-3.3-70b-versatile`) |
| `--no-mermaid` | Disable mermaid diagram generation |
| `--force` | Skip playlist videos without captions instead of aborting |

## Config file (`~/.config/notes-gen/config.yaml`)

Run `notegen config init` to generate a fully-commented template. Key sections:

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
