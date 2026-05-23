from __future__ import annotations

from rich.console import Console
from rich.table import Table

from notes_gen.processing.chunker import count_tokens

_COST_PER_1M: dict[str, float] = {
    "anthropic": 3.00,
    "openai": 2.50,
    "groq": 0.0,
    "gemini": 0.0,
    "ollama": 0.0,
    "together_ai": 0.90,
    "deepseek": 0.27,
    "mistral": 2.00,
    "cohere": 0.50,
    "nvidia_nim": 0.20,
    "xai": 2.00,
    "perplexity": 1.00,
}

_TOKENS_PER_SECOND = 60


def _provider(model: str) -> str:
    return model.split("/")[0] if "/" in model else model


def _cost(tokens: int, model: str) -> float:
    return tokens / 1_000_000 * _COST_PER_1M.get(_provider(model), 1.00)


def _cost_str(tokens: int, model: str) -> str:
    rate = _COST_PER_1M.get(_provider(model), 1.00)
    if rate == 0.0:
        return "free"
    return f"~${_cost(tokens, model):.4f}"


def _time_str(tokens: int) -> str:
    secs = max(1, tokens // _TOKENS_PER_SECOND)
    if secs < 60:
        return f"~{secs}s"
    return f"~{secs // 60}m {secs % 60}s"


def print_dry_run_summary(
    title: str,
    source: str,
    chunks: list[str],
    model: str,
) -> None:
    """Print dry-run summary for a single source."""
    print_dry_run_multi_summary([(title, source, chunks)], model)


def print_dry_run_multi_summary(
    entries: list[tuple[str, str, list[str]]],
    model: str,
) -> None:
    """Print dry-run summary table for multiple sources with totals row."""
    console = Console()
    multi = len(entries) > 1

    table = Table(box=None, show_header=True, padding=(0, 2))
    table.add_column("Title", style="cyan")
    table.add_column("Chunks", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Est. cost", justify="right")
    table.add_column("Est. time", justify="right")

    total_chunks = 0
    total_tokens = 0

    for title, source, chunks in entries:
        tokens = sum(count_tokens(c) for c in chunks)
        total_chunks += len(chunks)
        total_tokens += tokens
        label = title[:50] if multi else (source[:60] or title[:60])
        table.add_row(
            label,
            str(len(chunks)),
            f"{tokens:,}",
            _cost_str(tokens, model),
            _time_str(tokens),
        )

    if multi:
        table.add_section()
        table.add_row(
            "[bold]TOTAL[/]",
            f"[bold]{total_chunks}[/]",
            f"[bold]{total_tokens:,}[/]",
            f"[bold]{_cost_str(total_tokens, model)}[/]",
            f"[bold]{_time_str(total_tokens)}[/]",
        )

    console.print()
    console.print(table)
    console.print(f"  [dim]Model:[/] {model}  [dim]— no LLM call, no files written[/]\n")
