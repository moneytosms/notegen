from __future__ import annotations

import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
import litellm
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from notes_gen.config import Config

_console = Console(stderr=True)

# Per-key cooldown: key → monotonic time when it becomes available again
_key_cooldowns: dict[str, float] = {}

_SYSTEM_PROMPT = """\
You are a subject-matter expert writing personal reference notes. You have deep knowledge \
of whatever topic is in the content — not just what the source says, but everything a \
knowledgeable practitioner would know about the subject.

Your job is to produce a unified knowledge document, not a summary of the source.

Rules:
- Write in declarative, authoritative first-person-free prose. No "the author says", \
  "the video covers", "the speaker explains", or any meta-reference to the source.
- State facts directly: "S Pen supports 4096 pressure levels" not \
  "the video mentions S Pen support".
- Enrich beyond the source: add related technical context, comparisons, alternatives, \
  and implications that a knowledgeable person would include — seamlessly blended, \
  no markers distinguishing source from enrichment.
- Stay on topic — enrich within the subject domain, do not drift.
- Be dense and comprehensive. Never truncate. Notes should make someone want to read them.
- No scaffolding phrases: no "this section covers", "in summary", "as mentioned", "to conclude".
- Use Obsidian-flavored markdown: ## and ### headings only (no frontmatter — added externally).
- Use `> [!TIP]` callouts for non-obvious insights worth highlighting.
- Use `> [!WARNING]` callouts for gotchas, caveats, or common mistakes.
- Use mermaid diagrams for flows, architectures, and system relationships where useful.
- Use [[wikilinks]] for cross-references to related concepts.
- End your response with a line in this exact format (no blank line before it):
  TAGS: tag1, tag2, tag3
  (3-8 lowercase hyphenated tags inferred from content)
"""

_USER_PROMPT_TEMPLATE = """\
Write comprehensive expert notes on the following content. \
Synthesize it with your own knowledge of the subject — enrich, don't just extract.

<content>
{chunk}
</content>
"""


def _provider(model: str) -> str:
    return model.split("/")[0] if "/" in model else model


def _is_rate_limit_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return (
        "ratelimit" in name
        or "rate_limit" in name
        or " 429" in msg
        or "too many requests" in msg
        or "rate limit" in msg
    )


def _is_network_error(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, ConnectionError, TimeoutError)):
        return True
    msg = str(exc).lower()
    return any(code in msg for code in (" 500", " 502", " 503", " 504"))


def _available_keys(cfg: Config) -> list[str]:
    now = time.monotonic()
    provider = _provider(cfg.model)
    return [
        k
        for k in cfg.api_keys.get(provider, [])
        if k and not k.startswith("#") and _key_cooldowns.get(k, 0) <= now
    ]


def _cooldown_key(key: str | None, seconds: float) -> None:
    if key:
        _key_cooldowns[key] = time.monotonic() + seconds


def _parse_retry_after(exc: Exception) -> float | None:
    m = re.search(
        r"(?:retry.{0,15}after|retry_after|please\s+wait)[:\s]+(\d+(?:\.\d+)?)",
        str(exc),
        re.IGNORECASE,
    )
    return float(m.group(1)) if m else None


def _call_with_retry(cfg: Config, messages: list[dict]) -> str:
    for attempt in range(cfg.max_retries + 1):
        available = _available_keys(cfg)
        api_key = random.choice(available) if available else cfg.pick_api_key()

        try:
            kwargs: dict = {"model": cfg.model, "messages": messages, "temperature": 0.3}
            if api_key:
                kwargs["api_key"] = api_key
            response = litellm.completion(**kwargs)
            return response.choices[0].message.content

        except Exception as exc:
            is_rate = _is_rate_limit_error(exc)
            is_network = _is_network_error(exc)
            if (not is_rate and not is_network) or attempt >= cfg.max_retries:
                raise

            backoff = cfg.retry_base_delay * (2**attempt)

            if is_rate:
                _cooldown_key(api_key, backoff)
                still_available = _available_keys(cfg)
                if still_available:
                    _console.print(
                        f"[yellow]Rate limited — rotating to another key "
                        f"(attempt {attempt + 1}/{cfg.max_retries})...[/yellow]"
                    )
                    continue
                wait = _parse_retry_after(exc) or backoff
                _console.print(
                    f"[yellow]Rate limited on {_provider(cfg.model)} — "
                    f"waiting {wait:.0f}s (attempt {attempt + 1}/{cfg.max_retries})...[/yellow]"
                )
                time.sleep(wait)
            else:
                _console.print(
                    f"[yellow]Network error — retrying in {backoff:.0f}s "
                    f"(attempt {attempt + 1}/{cfg.max_retries})...[/yellow]"
                )
                time.sleep(backoff)

    raise RuntimeError("Max retries exceeded")  # pragma: no cover


_TAGS_RE = re.compile(r"\nTAGS:\s*(.+)$", re.IGNORECASE)


def _extract_tags(text: str) -> tuple[str, list[str]]:
    m = _TAGS_RE.search(text)
    if not m:
        return text, []
    tags = [t.strip().lower() for t in m.group(1).split(",") if t.strip()]
    clean = text[: m.start()].rstrip()
    return clean, tags


def _make_messages(chunk: str, format_suffix: str = "", extra_prompt: str = "") -> list[dict]:
    system = _SYSTEM_PROMPT + format_suffix
    if extra_prompt:
        system += f"\n\nAdditional instructions:\n{extra_prompt}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": _USER_PROMPT_TEMPLATE.format(chunk=chunk)},
    ]


_COMPRESS_PROMPT = """\
Condense the following notes to at most {target_words} words while preserving all key concepts,
code examples, and callouts. Keep the structure intact. Output only the condensed notes.
"""


def compress_notes(notes: str, target_tokens: int, cfg: Config) -> str:
    from notes_gen.processing.chunker import count_tokens

    current = count_tokens(notes)
    if current <= target_tokens:
        return notes

    target_words = int(target_tokens * 0.75)
    if cfg.verbose:
        _console.print(
            f"[dim]Compressing output from {current} → target {target_tokens} tokens...[/dim]"
        )
    messages = [
        {"role": "system", "content": _COMPRESS_PROMPT.format(target_words=target_words)},
        {"role": "user", "content": notes},
    ]
    return _call_with_retry(cfg, messages)


def generate_notes(
    chunks: list[str],
    cfg: Config,
    max_chunk_workers: int = 0,
) -> tuple[str, list[str]]:
    if not chunks:
        return "", []

    from notes_gen.output.formats import format_prompt_suffix

    fmt_suffix = format_prompt_suffix(cfg.output_format)
    extra = cfg.extra_prompt

    if cfg.verbose:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        total_tokens = sum(len(enc.encode(c)) for c in chunks)
        _console.print(
            f"[dim]notegen: {len(chunks)} chunk(s), ~{total_tokens} tokens, "
            f"model={cfg.model}[/dim]",
        )

    if len(chunks) == 1:
        with Progress(
            SpinnerColumn(),
            TextColumn("[dim]{task.description}[/dim]"),
            transient=True,
            console=_console,
        ) as bar:
            bar.add_task(f"Generating via {cfg.model}", total=None)
            raw = _call_with_retry(cfg, _make_messages(chunks[0], fmt_suffix, extra))
        return _extract_tags(raw)

    results: list[str | None] = [None] * len(chunks)
    workers = max_chunk_workers if max_chunk_workers > 0 else min(len(chunks), cfg.max_concurrent)

    with Progress(
        SpinnerColumn(),
        TextColumn("[dim]{task.description}[/dim]"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        transient=True,
        console=_console,
    ) as bar:
        task = bar.add_task(f"Generating via {cfg.model}", total=len(chunks))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_idx = {
                pool.submit(_call_with_retry, cfg, _make_messages(chunk, fmt_suffix, extra)): i
                for i, chunk in enumerate(chunks)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                results[idx] = future.result()
                bar.advance(task)

    all_tags: list[str] = []
    clean_parts: list[str] = []
    for r in results:
        if r:
            part, tags = _extract_tags(r)
            clean_parts.append(part)
            all_tags.extend(t for t in tags if t not in all_tags)
    return "\n\n".join(clean_parts), all_tags
