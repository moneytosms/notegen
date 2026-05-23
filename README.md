# notegen

Convert YouTube videos, playlists, and web pages into structured Obsidian-flavored markdown notes using LLMs.

## Install

```bash
pip install notegen
```

## Usage

```bash
# Auto-detect source type
notegen https://youtube.com/watch?v=...
notegen https://example.com/article
notegen transcript.txt

# Explicit commands
notegen video <youtube-url>
notegen playlist <playlist-url> [--force]
notegen web <url>
notegen text <file-or-stdin>

# Config
notegen config init   # create ~/.config/notes-gen/config.yaml
notegen config show   # print resolved config
```

## Options

| Flag | Description |
|---|---|
| `-o / --output-dir` | Override output directory |
| `-m / --model` | LiteLLM model string (e.g. `openai/gpt-4o`) |
| `--no-mermaid` | Disable mermaid diagram generation |
| `--force` | Skip playlist videos without captions instead of aborting |

## Config file (`~/.config/notes-gen/config.yaml`)

```yaml
output_dir: ~/notes
model: anthropic/claude-sonnet-4-6
mermaid: true
max_concurrent: 5
web_max_pages: 50
web_max_depth: 3
```

API keys are read from environment variables (e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).

## Output format

Obsidian-flavored markdown with YAML frontmatter, `## / ###` headings, `> [!TIP]` / `> [!WARNING]` callouts, mermaid diagrams, and `[[wikilinks]]`.

## Requirements

- Python ≥ 3.11
- An API key for your chosen LLM provider
