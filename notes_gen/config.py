from __future__ import annotations

import os
import random
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "notes-gen" / "config.yaml"
DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"


@dataclass
class Config:
    output_dir: Path = None  # type: ignore[assignment]
    model: str = DEFAULT_MODEL
    mermaid: bool = True
    max_concurrent: int = 5
    web_max_pages: int = 50
    web_max_depth: int = 3
    api_keys: dict[str, list[str]] = field(default_factory=dict)
    max_retries: int = 5
    retry_base_delay: float = 60.0
    verbose: bool = False
    cache: bool = True
    dry_run: bool = False
    max_output_tokens: int = 0
    merger_similarity_threshold: float = 0.7
    output_format: str = "obsidian"
    extra_prompt: str = ""

    def __post_init__(self) -> None:
        if self.output_dir is None:
            self.output_dir = Path.home() / "notes"
        self.output_dir = Path(self.output_dir)

    def pick_api_key(self) -> str | None:
        """Return a random key for the active provider, or None if not configured."""
        provider = self.model.split("/")[0] if "/" in self.model else self.model
        keys = [k for k in self.api_keys.get(provider, []) if k and not k.startswith("#")]
        if keys:
            return random.choice(keys)
        env_var = f"NOTEGEN_{provider.upper().replace('-', '_').replace('/', '_')}_KEY"
        env_key = os.environ.get(env_var)
        return env_key or None


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    if not path.exists():
        return Config()
    raw = yaml.safe_load(path.read_text()) or {}
    kwargs: dict = {}
    if "output_dir" in raw:
        kwargs["output_dir"] = Path(raw["output_dir"]).expanduser()
    scalar_fields = (
        "model",
        "mermaid",
        "max_concurrent",
        "web_max_pages",
        "web_max_depth",
        "max_retries",
        "retry_base_delay",
        "verbose",
        "cache",
        "max_output_tokens",
        "merger_similarity_threshold",
        "output_format",
        "extra_prompt",
    )
    for f in scalar_fields:
        if f in raw:
            kwargs[f] = raw[f]
    if "api_keys" in raw and isinstance(raw["api_keys"], dict):
        cleaned: dict[str, list[str]] = {}
        for provider, keys in raw["api_keys"].items():
            if isinstance(keys, list):
                cleaned[provider] = [str(k) for k in keys if k]
        kwargs["api_keys"] = cleaned
    return Config(**kwargs)


def merge_cli_overrides(
    cfg: Config,
    *,
    output_dir: Optional[Path] = None,
    model: Optional[str] = None,
    mermaid: Optional[bool] = None,
    verbose: Optional[bool] = None,
    cache: Optional[bool] = None,
    dry_run: Optional[bool] = None,
    output_format: Optional[str] = None,
    extra_prompt: Optional[str] = None,
) -> Config:
    overrides: dict = {}
    if output_dir is not None:
        overrides["output_dir"] = output_dir
    if model is not None:
        overrides["model"] = model
    if mermaid is not None:
        overrides["mermaid"] = mermaid
    if verbose is not None:
        overrides["verbose"] = verbose
    if cache is not None:
        overrides["cache"] = cache
    if dry_run is not None:
        overrides["dry_run"] = dry_run
    if output_format is not None:
        overrides["output_format"] = output_format
    if extra_prompt is not None:
        overrides["extra_prompt"] = extra_prompt
    return replace(cfg, **overrides)


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
model: anthropic/claude-sonnet-4-6

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
#   With 5 retries and base 60s: waits 60 → 120 → 240 → 480 → 960 seconds.
#   Generous defaults intentionally — free tiers often have 1 req/min limits.
max_retries: 5
retry_base_delay: 60.0
# verbose: false  # set true to show chunk counts, token usage, model/key selection
"""
