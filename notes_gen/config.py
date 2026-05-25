from __future__ import annotations

import os
import random
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "notes-gen" / "config.yaml"
DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"


def provider_of(model: str) -> str:
    return model.split("/")[0] if "/" in model else model


class Config(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    output_dir: Path = Field(default_factory=lambda: Path.home() / "notes")
    model: str = DEFAULT_MODEL
    api_base: str | None = None
    mermaid: bool = True
    max_concurrent: int = 5
    web_max_pages: int = 50
    web_max_depth: int = 3
    api_keys: dict[str, list[str]] = Field(default_factory=dict)
    max_retries: int = 5
    retry_base_delay: float = 60.0
    verbose: bool = False
    cache: bool = True
    dry_run: bool = False
    max_output_tokens: int = 0
    merger_similarity_threshold: float = 0.7
    output_format: str = "obsidian"
    extra_prompt: str = ""
    language: str = "en"
    incremental: bool = True
    download_images: bool = True
    prompt_templates: dict[str, str] = Field(default_factory=dict)
    toc: bool = False

    @field_validator("output_dir", mode="before")
    @classmethod
    def parse_path(cls, v: str | Path) -> Path:
        if isinstance(v, str):
            return Path(v).expanduser()
        return v

    def pick_api_key(self) -> str | None:
        provider = provider_of(self.model)
        keys = [k for k in self.api_keys.get(provider, []) if k and not k.startswith("#")]
        if keys:
            return random.choice(keys)
        env_var = f"NOTEGEN_{provider.upper().replace('-', '_').replace('/', '_')}_KEY"
        env_key = os.environ.get(env_var)
        return env_key or None


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    if not path.exists():
        return Config()

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        raw = {}

    # Ensure api_keys is cleaned
    if "api_keys" in raw and isinstance(raw["api_keys"], dict):
        cleaned: dict[str, list[str]] = {}
        for provider, keys in raw["api_keys"].items():
            if isinstance(keys, list):
                cleaned[provider] = [str(k) for k in keys if k]
        raw["api_keys"] = cleaned

    return Config(**raw)


def merge_cli_overrides(
    cfg: Config,
    **kwargs,
) -> Config:
    # Filter out None values to avoid overriding with defaults
    overrides = {k: v for k, v in kwargs.items() if v is not None}

    # Special handling for prompt templates and extra prompt
    template = overrides.pop("template", None)
    if template and template in cfg.prompt_templates:
        tpl_content = cfg.prompt_templates[template]
        current_extra = overrides.get("extra_prompt") or cfg.extra_prompt
        if current_extra:
            overrides["extra_prompt"] = f"{current_extra}\n\n{tpl_content}"
        else:
            overrides["extra_prompt"] = tpl_content

    # Create new config with overrides
    return cfg.model_copy(update=overrides)


CONFIG_TEMPLATE = """\
# notegen configuration
# Docs: https://github.com/moneytosms/notegen

# ── Output ───────────────────────────────────────────────────────────────────
output_dir: ~/notes
mermaid: true

# ── Model ────────────────────────────────────────────────────────────────────
# LiteLLM model string format: <provider>/<model-name>
# The provider prefix must match a key under api_keys below.
#
# Examples:
#   anthropic/claude-sonnet-4-6
#   openai/gpt-4o
#   openai/gpt-4o-mini
#   groq/llama-3.3-70b-versatile
#   groq/mixtral-8x7b-32768
#   gemini/gemini-1.5-pro
#   gemini/gemini-2.0-flash
#   nvidia_nim/meta/llama-3.3-70b-instruct  # free tier — build.nvidia.com
#   nvidia_nim/meta/llama-3.1-70b-instruct
#   nvidia_nim/mistralai/mixtral-8x7b-instruct
#   mistral/mistral-large-latest
#   cohere/command-r-plus
#   together_ai/meta-llama/Llama-3-70b-chat-hf
#   deepseek/deepseek-chat
#   ollama/llama3                   # local, no key needed
# model: anthropic/claude-sonnet-4-6
model: anthropic/claude-sonnet-4-6

# Optional: API base URL for local LLMs (Ollama, LM Studio) or proxies
# api_base: http://localhost:11434

# ── API Keys ──────────────────────────────────────────────────────────────────
# Add multiple keys per provider — notegen picks one at random per request
# (useful for rate-limit rotation across multiple free-tier accounts).
# Remove the leading '#' and paste your key to activate.
# Keys are never sent anywhere except the provider's own API.
api_keys:

  # Anthropic — https://console.anthropic.com/settings/keys
  anthropic:
    # - sk-ant-api03-XXXX

  # OpenAI — https://platform.openai.com/api-keys
  openai:
    # - sk-proj-XXXX

  # Groq (free tier, very fast) — https://console.groq.com/keys
  groq:
    # - gsk_XXXX

  # Google Gemini — https://aistudio.google.com/app/apikey
  gemini:
    # - AIzaSyXXXX

  # NVIDIA NIM (free tier) — https://build.nvidia.com — key format: nvapi-XXXX
  nvidia_nim:
    # - nvapi-XXXX

  # Mistral — https://console.mistral.ai/api-keys/
  mistral:
    # - XXXX

  # Cohere — https://dashboard.cohere.com/api-keys
  cohere:
    # - XXXX

  # Together AI — https://api.together.xyz/settings/api-keys
  together_ai:
    # - XXXX

  # DeepSeek — https://platform.deepseek.com/api_keys
  deepseek:
    # - sk-XXXX

  # Perplexity — https://www.perplexity.ai/settings/api
  perplexity:
    # - pplx-XXXX

  # XAI (Grok) — https://console.x.ai/
  xai:
    # - xai-XXXX

# Env var fallback: if no keys in config for a provider, notegen checks
# NOTEGEN_<PROVIDER>_KEY env var (e.g. NOTEGEN_GROQ_KEY, NOTEGEN_ANTHROPIC_KEY,
# NOTEGEN_NVIDIA_NIM_KEY).

# ── Concurrency & Web crawl ───────────────────────────────────────────────────
max_concurrent: 5    # parallel YouTube transcript fetches
web_max_pages: 50    # max pages per web crawl
web_max_depth: 3     # max link-follow depth

# ── Rate limiting & Retry ─────────────────────────────────────────────────────
# Free-tier providers (Groq, Gemini, Together AI, etc.) enforce strict TPM/RPM
# limits. notegen handles 429 errors gracefully:
#   1. Cool down the offending key and rotate to another key (if available).
#   2. If all keys are exhausted, wait using the Retry-After header value,
#      or exponential backoff (retry_base_delay * 2^attempt), then retry.
#
# max_retries: total retry attempts per LLM call (default 5).
# retry_base_delay: base wait in seconds for exponential backoff (default 60).

# ── Behavior ──────────────────────────────────────────────────────────────────
# Target language for notes (ISO 639-1 code, e.g. en, es, fr, de, hi)
language: en

# Skip videos in a playlist if the .md note already exists
incremental: true

# ── Templates ─────────────────────────────────────────────────────────────────
# Reusable prompt snippets to change note style.
# Use via: notegen video <url> --template code
prompt_templates:
  code: "Focus on implementation details, code blocks, and syntax. Minimize theoretical fluff."
  theory: "Focus on high-level architecture and design patterns. Keep code samples brief."
#   With 5 retries and base 60s: waits 60 → 120 → 240 → 480 → 960 seconds.
#   Generous defaults intentionally — free tiers often have 1 req/min limits.
max_retries: 5
retry_base_delay: 60.0
# verbose: false  # set true to show chunk counts, token usage, model/key selection
"""
