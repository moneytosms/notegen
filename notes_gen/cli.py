import logging
import platform
import subprocess
from pathlib import Path
from typing import Optional

import typer
import yaml

logging.getLogger("LiteLLM").setLevel(logging.ERROR)

from notes_gen.config import (
    CONFIG_TEMPLATE,
    DEFAULT_CONFIG_PATH,
    Config,
    load_config,
    merge_cli_overrides,
)

app = typer.Typer(no_args_is_help=False, help="Convert YouTube/web content to Obsidian notes.")
config_app = typer.Typer(help="Manage configuration.")
cache_app = typer.Typer(help="Manage local cache.")
app.add_typer(config_app, name="config")
app.add_typer(cache_app, name="cache")

_KNOWN_SUBCOMMANDS = {
    "video", "playlist", "web", "text", "config", "cache", "auto", "doctor", "watch"
}

_KNOWN_CONFIG_FIELDS = {
    "output_dir", "mermaid", "model", "api_keys",
    "max_concurrent", "web_max_pages", "web_max_depth",
    "max_retries", "retry_base_delay", "verbose", "cache",
    "max_output_tokens", "merger_similarity_threshold", "output_format",
}


def _run_auto(source: str, cfg: Config, force: bool = False) -> None:
    if "youtube.com/playlist" in source or ("list=" in source and "youtube.com" in source):
        from notes_gen.sources.youtube import run_playlist_pipeline

        index_path = run_playlist_pipeline(source, cfg, force=force)
        typer.echo(f"Playlist notes written to {index_path.parent}")
    elif "youtube.com/watch" in source or "youtu.be/" in source:
        from notes_gen.sources.youtube import run_video_pipeline

        output_path = run_video_pipeline(source, cfg)
        typer.echo(f"Notes written to {output_path}")
    elif source.startswith("http://") or source.startswith("https://"):
        from notes_gen.sources.web import run_web_crawl_pipeline

        output_path = run_web_crawl_pipeline(source, cfg)
        typer.echo(f"Notes written to {output_path}")
    else:
        from notes_gen.sources.text import run_text_pipeline

        output_path = run_text_pipeline(source, cfg)
        typer.echo(f"Notes written to {output_path}")


@cache_app.command("clear")
def cache_clear() -> None:
    """Remove all cached transcripts and notes from ~/.cache/notegen/."""
    from notes_gen.cache import clear_cache

    n = clear_cache()
    typer.echo(f"Cleared {n} cache file(s).")


@config_app.command("init")
def config_init() -> None:
    """Create default config at ~/.config/notes-gen/config.yaml."""
    if DEFAULT_CONFIG_PATH.exists():
        typer.echo(f"Config already exists: {DEFAULT_CONFIG_PATH}")
        raise typer.Exit(1)
    DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_CONFIG_PATH.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    typer.echo(f"Config written to {DEFAULT_CONFIG_PATH}")
    typer.echo("Next: run `notegen config open` to add your API key.")


@config_app.command("open")
def config_open() -> None:
    """Open config file in your default editor (creates it first if missing)."""
    if not DEFAULT_CONFIG_PATH.exists():
        DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_CONFIG_PATH.write_text(CONFIG_TEMPLATE, encoding="utf-8")
        typer.echo(f"Config created: {DEFAULT_CONFIG_PATH}")

    typer.echo(f"Opening {DEFAULT_CONFIG_PATH}")
    system = platform.system()
    if system == "Windows":
        import os

        os.startfile(str(DEFAULT_CONFIG_PATH))  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.run(["open", str(DEFAULT_CONFIG_PATH)], check=False)
    else:
        subprocess.run(["xdg-open", str(DEFAULT_CONFIG_PATH)], check=False)


@config_app.command("validate")
def config_validate() -> None:
    """Check config file structure, model string, and API key presence."""
    import os

    from rich.console import Console

    console = Console()
    ok = True

    def _pass(msg: str) -> None:
        console.print(f"  [green]✓[/] {msg}")

    def _fail(msg: str) -> None:
        nonlocal ok
        ok = False
        console.print(f"  [red]✗[/] {msg}")

    console.print("\n[bold]notegen config validate[/]\n")

    if not DEFAULT_CONFIG_PATH.exists():
        _fail(f"Config not found: {DEFAULT_CONFIG_PATH}")
        console.print()
        raise typer.Exit(1)
    _pass(f"Config found: {DEFAULT_CONFIG_PATH}")

    try:
        raw = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        _fail(f"Invalid YAML: {e}")
        console.print()
        raise typer.Exit(1)
    _pass("Valid YAML")

    unknown = set(raw.keys()) - _KNOWN_CONFIG_FIELDS
    if unknown:
        _fail(f"Unknown fields: {', '.join(sorted(unknown))}")
    else:
        _pass("No unknown fields")

    model = raw.get("model", "anthropic/claude-sonnet-4-6")
    if "/" not in str(model):
        _fail(f"Model string missing provider prefix: {model!r} (expected <provider>/<model>)")
    else:
        _pass(f"Model format OK: {model}")

    provider = str(model).split("/")[0]
    keys = raw.get("api_keys", {})
    provider_keys = [k for k in keys.get(provider, []) if k and not str(k).startswith("#")]
    env_var = f"NOTEGEN_{provider.upper().replace('-', '_').replace('/', '_')}_KEY"
    has_env = bool(os.environ.get(env_var))
    if provider_keys:
        _pass(f"API key(s) configured for {provider!r} ({len(provider_keys)} key(s))")
    elif has_env:
        _pass(f"API key found via {env_var} env var")
    else:
        _fail(
            f"No API key for provider {provider!r} — add to config or set {env_var}"
        )

    console.print()
    if ok:
        console.print("[green]Config is valid.[/]\n")
        raise typer.Exit(0)
    else:
        console.print("[red]Config has issues — fix them before running notegen.[/]\n")
        raise typer.Exit(1)


@config_app.command("show")
def config_show() -> None:
    """Print resolved config as YAML."""
    cfg = load_config()
    data = {
        "output_dir": str(cfg.output_dir),
        "model": cfg.model,
        "mermaid": cfg.mermaid,
        "max_concurrent": cfg.max_concurrent,
        "web_max_pages": cfg.web_max_pages,
        "web_max_depth": cfg.web_max_depth,
        "max_retries": cfg.max_retries,
        "retry_base_delay": cfg.retry_base_delay,
        "verbose": cfg.verbose,
    }
    typer.echo(yaml.dump(data, default_flow_style=False), nl=False)


@app.command()
def doctor(
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="Test a specific provider (overrides config model)"
    ),
) -> None:
    """Health check: validate config + make a real test API call."""
    import time

    import litellm
    from rich.console import Console

    console = Console()
    console.print("\n[bold]notegen doctor[/]\n")

    cfg = load_config(DEFAULT_CONFIG_PATH)

    if provider:
        cfg = merge_cli_overrides(cfg, model=f"{provider}/{cfg.model.split('/')[-1]}")

    # run config validate inline
    import os

    ok = True

    def _pass(msg: str) -> None:
        console.print(f"  [green]✓[/] {msg}")

    def _fail(msg: str) -> None:
        nonlocal ok
        ok = False
        console.print(f"  [red]✗[/] {msg}")

    _pass(f"Config path: {DEFAULT_CONFIG_PATH}")
    if not DEFAULT_CONFIG_PATH.exists():
        _fail("Config file missing — run `notegen config init`")
        raise typer.Exit(1)

    raw: dict = {}
    try:
        raw = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        _pass("Valid YAML")
    except Exception as e:
        _fail(f"Invalid YAML: {e}")
        raise typer.Exit(1)

    model = raw.get("model", cfg.model)
    if "/" not in str(model):
        _fail(f"Model missing provider prefix: {model!r}")
        ok = False
    else:
        _pass(f"Model: {model}")

    prov = str(model).split("/")[0]
    all_keys = [
        k for k in raw.get("api_keys", {}).get(prov, []) if k and not str(k).startswith("#")
    ]
    env_var = f"NOTEGEN_{prov.upper().replace('-', '_').replace('/', '_')}_KEY"
    has_env = bool(os.environ.get(env_var))
    if all_keys:
        n = len(all_keys)
        _pass(f"API keys for {prov!r}: {n} configured")
    elif has_env:
        _pass(f"API key via {env_var}")
    else:
        _fail(f"No API key for {prov!r}")
        ok = False

    if not ok:
        console.print("\n[red]Config issues found — fix before continuing.[/]\n")
        raise typer.Exit(1)

    # real API call
    console.print(f"\n[dim]Sending test request to {cfg.model}...[/]")
    api_key = cfg.pick_api_key()
    masked = None
    if all_keys and api_key:
        idx = all_keys.index(api_key) + 1 if api_key in all_keys else 1
        masked = f"key-{idx}/{len(all_keys)}"

    try:
        t0 = time.monotonic()
        kwargs: dict = {
            "model": cfg.model,
            "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
            "max_tokens": 5,
            "temperature": 0,
        }
        if api_key:
            kwargs["api_key"] = api_key
        resp = litellm.completion(**kwargs)
        latency_ms = int((time.monotonic() - t0) * 1000)
        reply = resp.choices[0].message.content.strip()
    except Exception as exc:
        _fail(f"API call failed: {exc}")
        console.print("\n[red]Doctor found issues.[/]\n")
        raise typer.Exit(1)

    _pass(f"API call succeeded — latency {latency_ms}ms, reply: {reply!r}")
    if masked:
        _pass(f"Key used: {masked}")
    console.print("\n[green]Doctor OK — notegen is ready.[/]\n")
    raise typer.Exit(0)


@app.command()
def video(
    url: str = typer.Argument(..., help="YouTube video URL"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    no_mermaid: bool = typer.Option(False, "--no-mermaid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    force: bool = typer.Option(False, "--force"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Print estimate; skip LLM"),
    fmt: Optional[str] = typer.Option(None, "--format", help="obsidian|logseq|plain|roam"),
) -> None:
    """Generate notes from a YouTube video."""
    from notes_gen.sources.youtube import run_video_pipeline

    cfg = load_config()
    cfg = merge_cli_overrides(
        cfg, output_dir=output_dir, model=model, mermaid=not no_mermaid,
        verbose=verbose, cache=not no_cache, dry_run=dry_run or None,
        output_format=fmt,
    )
    output_path = run_video_pipeline(url, cfg)
    typer.echo(f"Notes written to {output_path}")


@app.command()
def playlist(
    url: str = typer.Argument(..., help="YouTube playlist URL"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    no_mermaid: bool = typer.Option(False, "--no-mermaid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    force: bool = typer.Option(False, "--force"),
    force_restart: bool = typer.Option(False, "--force-restart", help="Ignore progress file"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Print estimate; skip LLM"),
    fmt: Optional[str] = typer.Option(None, "--format", help="obsidian|logseq|plain|roam"),
) -> None:
    """Generate notes from a YouTube playlist."""
    from notes_gen.sources.youtube import run_playlist_pipeline

    cfg = load_config()
    cfg = merge_cli_overrides(
        cfg, output_dir=output_dir, model=model, mermaid=not no_mermaid,
        verbose=verbose, cache=not no_cache, dry_run=dry_run or None,
        output_format=fmt,
    )
    index_path = run_playlist_pipeline(url, cfg, force=force, force_restart=force_restart)
    typer.echo(f"Playlist notes written to {index_path.parent}")


@app.command()
def web(
    url: str = typer.Argument(..., help="Web URL to fetch"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    no_mermaid: bool = typer.Option(False, "--no-mermaid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Print estimate; skip LLM"),
    fmt: Optional[str] = typer.Option(None, "--format", help="obsidian|logseq|plain|roam"),
) -> None:
    """Generate notes from a web page (crawls same-domain links)."""
    from notes_gen.sources.web import run_web_crawl_pipeline

    cfg = load_config()
    cfg = merge_cli_overrides(
        cfg, output_dir=output_dir, model=model, mermaid=not no_mermaid,
        verbose=verbose, cache=not no_cache, dry_run=dry_run or None,
        output_format=fmt,
    )
    output_path = run_web_crawl_pipeline(url, cfg)
    typer.echo(f"Notes written to {output_path}")


@app.command()
def text(
    source: str = typer.Argument(..., help="File path or '-' for stdin"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    no_mermaid: bool = typer.Option(False, "--no-mermaid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Print estimate; skip LLM"),
    fmt: Optional[str] = typer.Option(None, "--format", help="obsidian|logseq|plain|roam"),
) -> None:
    """Generate notes from a text file or stdin."""
    from notes_gen.sources.text import run_text_pipeline

    cfg = load_config()
    cfg = merge_cli_overrides(
        cfg, output_dir=output_dir, model=model, mermaid=not no_mermaid,
        verbose=verbose, cache=not no_cache, dry_run=dry_run or None,
        output_format=fmt,
    )
    output_path = run_text_pipeline(source, cfg)
    typer.echo(f"Notes written to {output_path}")


@app.command()
def auto(
    source: str = typer.Argument(..., help="YouTube URL, web URL, or file path"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    no_mermaid: bool = typer.Option(False, "--no-mermaid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    force: bool = typer.Option(False, "--force"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Print estimate; skip LLM"),
    fmt: Optional[str] = typer.Option(None, "--format", help="obsidian|logseq|plain|roam"),
) -> None:
    """Auto-detect source type and generate notes."""
    cfg = load_config()
    cfg = merge_cli_overrides(
        cfg, output_dir=output_dir, model=model, mermaid=not no_mermaid,
        verbose=verbose, cache=not no_cache, dry_run=dry_run or None,
        output_format=fmt,
    )
    _run_auto(source, cfg, force=force)


@app.command()
def watch(
    directory: Path = typer.Argument(..., help="Directory to watch for new .txt/.md files"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    fmt: Optional[str] = typer.Option(None, "--format", help="obsidian|logseq|plain|roam"),
) -> None:
    """Watch a directory and auto-process new .txt/.md files."""
    from notes_gen.sources.watch import run_watch

    cfg = load_config()
    cfg = merge_cli_overrides(
        cfg,
        output_dir=output_dir or directory,
        model=model,
        verbose=verbose,
        cache=not no_cache,
        output_format=fmt,
    )
    run_watch(directory, cfg)


def _show_rich_help() -> None:
    from importlib.metadata import version as _ver

    from rich.console import Console
    from rich.table import Table

    try:
        ver = _ver("notegen")
    except Exception:
        ver = "dev"

    console = Console()
    console.print(
        f"\n[bold cyan]notegen[/] [dim]v{ver}[/]  —  "
        "YouTube · playlists · web pages → Obsidian notes\n"
    )

    def _table() -> Table:
        t = Table(box=None, show_header=False, padding=(0, 2, 0, 2), expand=False)
        t.add_column(no_wrap=True, style="green")
        t.add_column(style="dim")
        return t

    console.print("[bold]SETUP[/] [dim](first time)[/]")
    t = _table()
    t.add_row("notegen config init", "create config file")
    t.add_row("notegen config open", "open it and add your API key")
    t.add_row("notegen <url-or-file>", "generate notes")
    console.print(t)

    console.print("\n[bold]USAGE[/]")
    t = _table()
    t.add_row("notegen <youtube-watch-url>", "video → single note")
    t.add_row("notegen <youtube-playlist-url>", "playlist → folder + index.md")
    t.add_row("notegen <https://...>", "crawl web page → notes")
    t.add_row("notegen <file.txt>", "local text / transcript")
    t.add_row("notegen text -", "read from stdin")
    console.print(t)

    console.print("\n[bold]CONFIG COMMANDS[/]")
    t = _table()
    t.add_row("notegen config init", "create config")
    t.add_row("notegen config open", "open in default editor")
    t.add_row("notegen config show", "print resolved config")
    t.add_row("notegen config validate", "check config structure + keys")
    t.add_row("notegen doctor", "validate config + test API connection")
    console.print(t)

    console.print("\n[bold]CACHE COMMANDS[/]")
    t = _table()
    t.add_row("notegen cache clear", "remove all cached transcripts + notes")
    console.print(t)

    console.print("\n[bold]WATCH[/]")
    t = _table()
    t.add_row("notegen watch <dir>", "auto-process new .txt/.md files dropped in dir")
    console.print(t)

    console.print("\n[bold]OPTIONS[/] [dim](apply to all commands)[/]")
    t = Table(box=None, show_header=False, padding=(0, 2, 0, 2), expand=False)
    t.add_column(no_wrap=True, style="yellow")
    t.add_column(style="dim")
    t.add_row("-o / --output-dir PATH", "override output directory")
    t.add_row("-m / --model TEXT", "LiteLLM model  e.g. [green]groq/llama-3.3-70b-versatile[/]")
    t.add_row("-v / --verbose", "show chunk count, token usage, crawl status")
    t.add_row("--no-mermaid", "disable mermaid diagram generation")
    t.add_row("--no-cache", "skip cache read/write for this run")
    t.add_row("-n / --dry-run", "print token/cost estimate; skip LLM call")
    t.add_row("--format TEXT", "obsidian (default) | logseq | plain | roam")
    t.add_row("--force", "skip videos without captions (playlist)")
    t.add_row("--force-restart", "ignore playlist resume file, reprocess all")
    console.print(t)

    console.print("\n[bold]CONFIG FILE[/]")
    console.print("  [dim]Linux/macOS[/]  [green]~/.config/notes-gen/config.yaml[/]")
    win_path = r"%USERPROFILE%\.config\notes-gen\config.yaml"
    console.print(f"  [dim]Windows[/]     [green]{win_path}[/]\n")


def main() -> None:
    """Entry point: show rich help or inject 'auto' subcommand for bare URL/file."""
    import sys

    if sys.platform == "win32":
        for _stream in ("stdout", "stderr"):
            _s = getattr(sys, _stream, None)
            if _s is not None and hasattr(_s, "reconfigure"):
                _s.reconfigure(encoding="utf-8", errors="replace")

    args = sys.argv[1:]
    if not args or args == ["--help"] or args == ["-h"]:
        _show_rich_help()
        return
    if args and not args[0].startswith("-") and args[0] not in _KNOWN_SUBCOMMANDS:
        sys.argv.insert(1, "auto")
    app()
