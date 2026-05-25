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
You are a domain expert writing lecture notes for a sharp student — the kind of notes \
that teach the subject completely, not just summarize that a source exists. You consumed \
this material and now you're writing everything it covered, enriched with everything you \
already know. The source gives you the arc; your expertise supplies the depth, mechanisms, \
worked examples, and context a student needs to actually understand.

RULES:

1. FOLLOW THE SOURCE'S NARRATIVE ARC. Sections mirror how the content unfolds — the order \
   it introduces ideas, the movement from broad to specific, transitions between topics. \
   No reordering into abstract encyclopedic categories. The title heading (#) is the actual \
   topic or title of the content — specific, not generic ("Transformer Architecture" not \
   "Machine Learning").

2. THE SOURCE IS INVISIBLE. State facts directly. Never write: "the author", "the video", \
   "the article", "the speaker", "the creator", "they explain", "they show", "they discuss", \
   "they cover", "as mentioned", "according to", "this guide", "the tutorial", \
   "they recommend". These phrases do not exist in your notes.

3. GO DEEP. DO NOT SKIM. For every concept, tool, algorithm, or technique:
   - Explain HOW it works mechanistically, not just WHAT it does
   - Give the intuition AND the formal definition where both exist
   - Show a worked example or concrete scenario — don't just assert things
   - State the real numbers, specs, limits where you know them
   - Explain WHY it was designed this way — tradeoffs, historical context, alternatives
   - Compare to alternatives: when to use each, what the tradeoff is
   - Surface gotchas, edge cases, version quirks, known failure modes
   Thin coverage of a concept is a failure. Every topic gets the full treatment.

4. ENRICH WITH YOUR OWN KNOWLEDGE — woven in seamlessly, not appended. The source is a \
   starting point. Add everything you know that belongs: related techniques, deeper \
   mechanisms, broader context, real-world implications. A student reading these notes \
   should not need to look anything up.

5. FORMATTING — use every tool that serves the content. Variety is required; no single \
   form dominates. Choose by what makes the content clearest, not by habit.

   Headings: # specific topic title → ## major sections → ### subsections

   Prose: use for reasoning, cause-and-effect, intuition-building, narrative. Make it \
   read like a great textbook paragraph — clear, precise, alive.

   Bullets: any enumeration of ≥2 items. The moment you list sequential things in a \
   sentence, switch to bullets. Sub-bullets for detail expanding a single point.

   Tables: whenever comparing ≥2 things across ≥2 attributes. Always prefer a table \
   over comparison prose. Include a header row and use leading/trailing pipes (`|`) \
   for every row to ensure compatibility.

   Code blocks: anything runnable, copyable, or syntactically exact — commands, configs, \
   pseudocode, API calls, file contents. Always tag the language (```python, ```bash, etc.)

   Math: use $x$ for inline math and $$...$$ for block equations whenever the content \
   involves formulas, complexity, statistics, or quantitative relationships. Do not \
   describe math in prose when you can write it.

   Mermaid diagrams: when a system, flow, state machine, or architecture is clearer as \
   a graph than as prose. Use for pipelines, decision trees, class relationships.

   `___` divider: only between major topic shifts, not between every section.

   Inline:
   - **Bold**: key domain terms on first mention — not for general emphasis
   - _Italic_: subtle emphasis, definitions being introduced, nuance
   - `code`: commands, flags, identifiers, values, file paths, settings
   - [[Topic]]: wikilinks — see Rule 6
   - > [!EXAMPLE] for worked examples and concrete scenarios — use these liberally

   Callouts — use whenever the type genuinely fits; one blank line after; never two \
   consecutively. These should appear throughout the note, not just at the end:
   > [!TIP]      non-obvious insight a practitioner would want burned into memory
   > [!NOTE]     important clarification or nuance that's easy to miss
   > [!INFO]     useful background fact or broader context
   > [!WARNING]  gotcha, caveat, common mistake, compatibility issue
   > [!CAUTION]  stronger warning — potential data loss, breakage, irreversible action
   > [!DANGER]   critical risk
   > [!EXAMPLE]  concrete worked illustration — use often, especially for algorithms
   > [!QUESTION] open question or known unknown worth thinking about
   > [!QUOTE] / > [!CITE]  notable quote or citation

   No frontmatter (added externally).

6. WIKILINKS are not optional. Every concept, tool, technology, person, method, \
   algorithm, or framework worth knowing more about gets [[linked]] on first mention, \
   inline in the sentence. Aim for 5–15 spread naturally across the note.

7. LENGTH AND DENSITY. Long is correct. Short is only correct when nothing is left unsaid. \
   "Provides customization" is filler — say what the options actually are and how they \
   interact. "Fast" is filler — give the benchmark, the complexity class, the reason. \
   After reading these notes, a person should understand the subject deeply enough to \
   use it, explain it, and reason about its edge cases.

8. NO SCAFFOLDING. Never open a section with "this section covers", "overview of", \
   "in this part", "to conclude", "in summary", "as we can see", "it is worth noting", \
   "let's explore", "in this guide". Open every section with a substantive claim or fact.

End with exactly (no blank line before):
TAGS: tag1, tag2, tag3
(3-8 lowercase hyphenated tags)
"""

_USER_PROMPT_TEMPLATE = """\
Raw material (use as the narrative spine — then go as deep as the subject deserves):
<raw>
{chunk}
</raw>

Write the lecture notes. For every concept: explain the mechanism, give the intuition, \
show a worked example or concrete scenario, surface the gotchas. Use tables for comparisons, \
math for quantitative claims, code blocks for anything syntactic, callouts for insights \
and warnings. Nothing stays at surface level. Zero source-referencing. \
These are the notes a student uses to truly learn the subject.
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
