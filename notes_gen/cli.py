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
    "video",
    "playlist",
    "web",
    "text",
    "config",
    "cache",
    "auto",
    "doctor",
    "watch",
    "setup",
}

_KNOWN_CONFIG_FIELDS = {
    "output_dir",
    "mermaid",
    "model",
    "api_keys",
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
}

_PROVIDER_TEST_MODELS = {
    "anthropic": "anthropic/claude-haiku-4-5-20251001",
    "openai": "openai/gpt-4o-mini",
    "groq": "groq/llama-3.3-70b-versatile",
    "gemini": "gemini/gemini-2.0-flash",
    "nvidia_nim": "nvidia_nim/meta/llama-3.3-70b-instruct",
    "mistral": "mistral/mistral-small-latest",
    "deepseek": "deepseek/deepseek-chat",
    "together_ai": "together_ai/meta-llama/Llama-3-70b-chat-hf",
    "ollama": "ollama/llama3",
    "xai": "xai/grok-2",
    "cohere": "cohere/command-r-plus",
    "perplexity": "perplexity/sonar",
}

_PROVIDER_LIST = [
    ("groq", "free tier, fast (recommended)"),
    ("nvidia_nim", "free tier — build.nvidia.com"),
    ("gemini", "free tier"),
    ("anthropic", "paid"),
    ("openai", "paid"),
    ("mistral", "paid"),
    ("deepseek", "paid"),
    ("together_ai", "paid"),
    ("xai", "paid"),
    ("cohere", "paid"),
    ("perplexity", "paid"),
    ("ollama", "local, no key needed"),
]


def _get_version() -> str:
    import tomllib
    from importlib.metadata import version as _ver

    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            return str(data["project"]["version"])
        except Exception:
            pass

    try:
        return _ver("notegen")
    except Exception:
        return "dev"


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
    typer.echo("Tip: `notegen setup` is the recommended way to configure notegen")


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
        _fail(f"No API key for provider {provider!r} — add to config or set {env_var}")

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
        None, "--provider", help="Test a specific provider (overrides config model)"
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
        cfg = merge_cli_overrides(
            cfg, model=_PROVIDER_TEST_MODELS.get(provider, f"{provider}/unknown")
        )

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
        _fail("Config missing — run: notegen setup")
        raise typer.Exit(1)

    try:
        yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        _pass("Valid YAML")
    except Exception as e:
        _fail(f"Invalid YAML: {e}")
        raise typer.Exit(1)

    model = cfg.model
    if "/" not in str(model):
        _fail(f"Model missing provider prefix: {model!r}")
    else:
        _pass(f"Model: {model}")

    prov = str(model).split("/")[0]
    all_keys = [k for k in cfg.api_keys.get(prov, []) if k and not k.startswith("#")]
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
    prompt: Optional[str] = typer.Option(
        None, "--prompt", "-p", help="Extra instructions for LLM prompt"
    ),
) -> None:
    """Generate notes from a YouTube video."""
    from notes_gen.sources.youtube import run_video_pipeline

    cfg = load_config()
    cfg = merge_cli_overrides(
        cfg,
        output_dir=output_dir,
        model=model,
        mermaid=not no_mermaid,
        verbose=verbose,
        cache=not no_cache,
        dry_run=dry_run or None,
        output_format=fmt,
        extra_prompt=prompt,
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
    prompt: Optional[str] = typer.Option(
        None, "--prompt", "-p", help="Extra instructions for LLM prompt"
    ),
) -> None:
    """Generate notes from a YouTube playlist."""
    from notes_gen.sources.youtube import run_playlist_pipeline

    cfg = load_config()
    cfg = merge_cli_overrides(
        cfg,
        output_dir=output_dir,
        model=model,
        mermaid=not no_mermaid,
        verbose=verbose,
        cache=not no_cache,
        dry_run=dry_run or None,
        output_format=fmt,
        extra_prompt=prompt,
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
    prompt: Optional[str] = typer.Option(
        None, "--prompt", "-p", help="Extra instructions for LLM prompt"
    ),
) -> None:
    """Generate notes from a web page (crawls same-domain links)."""
    from notes_gen.sources.web import run_web_crawl_pipeline

    cfg = load_config()
    cfg = merge_cli_overrides(
        cfg,
        output_dir=output_dir,
        model=model,
        mermaid=not no_mermaid,
        verbose=verbose,
        cache=not no_cache,
        dry_run=dry_run or None,
        output_format=fmt,
        extra_prompt=prompt,
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
    prompt: Optional[str] = typer.Option(
        None, "--prompt", "-p", help="Extra instructions for LLM prompt"
    ),
) -> None:
    """Generate notes from a text file or stdin."""
    from notes_gen.sources.text import run_text_pipeline

    cfg = load_config()
    cfg = merge_cli_overrides(
        cfg,
        output_dir=output_dir,
        model=model,
        mermaid=not no_mermaid,
        verbose=verbose,
        cache=not no_cache,
        dry_run=dry_run or None,
        output_format=fmt,
        extra_prompt=prompt,
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
    prompt: Optional[str] = typer.Option(
        None, "--prompt", "-p", help="Extra instructions for LLM prompt"
    ),
) -> None:
    """Auto-detect source type and generate notes."""
    cfg = load_config()
    cfg = merge_cli_overrides(
        cfg,
        output_dir=output_dir,
        model=model,
        mermaid=not no_mermaid,
        verbose=verbose,
        cache=not no_cache,
        dry_run=dry_run or None,
        output_format=fmt,
        extra_prompt=prompt,
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


def _merge_config(
    path: Path,
    provider: str,
    model: str,
    output_dir: str,
    new_keys: list[str],
) -> None:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.exists() else {}

    if model:
        raw["model"] = model
    if output_dir and output_dir != "~/notes":
        raw["output_dir"] = output_dir

    if not isinstance(raw.get("api_keys"), dict):
        raw["api_keys"] = {}
    if not isinstance(raw["api_keys"].get(provider), list):
        raw["api_keys"][provider] = []

    existing = set(raw["api_keys"][provider])
    raw["api_keys"][provider].extend(k for k in new_keys if k and k not in existing)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True), encoding="utf-8")


@app.command()
def setup() -> None:
    """Interactive guided setup wizard — configure provider, model, API keys."""
    from rich.console import Console

    console = Console()
    console.print("\n[bold cyan]notegen setup[/] — guided configuration\n")

    # Step 1: Choose provider
    console.print("[bold]Available providers:[/]")
    for i, (prov, label) in enumerate(_PROVIDER_LIST, 1):
        console.print(f"  [green]{i:2}[/] {prov:<15} [dim]{label}[/]")

    console.print("\nChoose provider [Enter = groq]: ", end="")
    choice = input().strip()
    if not choice:
        provider = "groq"
    elif choice.isdigit() and 1 <= int(choice) <= len(_PROVIDER_LIST):
        provider = _PROVIDER_LIST[int(choice) - 1][0]
    else:
        provider = choice

    # Step 2: Choose model
    default_model = _PROVIDER_TEST_MODELS.get(provider, f"{provider}/unknown")
    console.print(f"\nModel [Enter = {default_model}]: ", end="")
    model_input = input().strip()
    model = model_input if model_input else default_model

    # Step 3: Output directory
    console.print("\nOutput directory [Enter = ~/notes]: ", end="")
    output_dir = input().strip() or "~/notes"

    # Step 4: API keys
    all_new_keys: list[str] = []
    if provider != "ollama":
        console.print(f"\nPaste API key(s) for [bold]{provider}[/] (blank line to stop):")
        while True:
            console.print("  key: ", end="")
            key = input().strip()
            if not key:
                break
            if key.startswith("#") or len(key) < 8:
                console.print("  [yellow]Skipped — looks like a placeholder[/]")
                continue
            all_new_keys.append(key)
            console.print("  [green]✓[/] added")

    # Step 5: Additional providers
    extra_providers: list[tuple[str, list[str]]] = []
    console.print("\nAdd keys for another provider? [y/N]: ", end="")
    if input().strip().lower() == "y":
        while True:
            console.print("Provider name (blank to stop): ", end="")
            extra_prov = input().strip()
            if not extra_prov:
                break
            extra_keys: list[str] = []
            console.print(f"Keys for {extra_prov} (blank to stop):")
            while True:
                console.print("  key: ", end="")
                k = input().strip()
                if not k:
                    break
                if not k.startswith("#") and len(k) >= 8:
                    extra_keys.append(k)
                    console.print("  [green]✓[/] added")
            if extra_keys:
                extra_providers.append((extra_prov, extra_keys))

    # Step 6: Write config
    existed = DEFAULT_CONFIG_PATH.exists()
    if not existed:
        DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_CONFIG_PATH.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    _merge_config(DEFAULT_CONFIG_PATH, provider, model, output_dir, all_new_keys)
    for ep, ek in extra_providers:
        _merge_config(DEFAULT_CONFIG_PATH, ep, "", "", ek)
    action = "updated" if existed else "created"
    console.print(f"\n[green]✓[/] Config {action}: {DEFAULT_CONFIG_PATH}")

    # Step 7: Run doctor
    console.print("\nRun doctor to verify connection? [Y/n]: ", end="")
    if input().strip().lower() != "n":
        try:
            import time

            import litellm

            cfg = load_config(DEFAULT_CONFIG_PATH)
            console.print(f"\n[dim]Testing {cfg.model}...[/]")
            api_key = cfg.pick_api_key()
            kwargs: dict = {
                "model": cfg.model,
                "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
                "max_tokens": 5,
                "temperature": 0,
            }
            if api_key:
                kwargs["api_key"] = api_key
            t0 = time.monotonic()
            resp = litellm.completion(**kwargs)
            ms = int((time.monotonic() - t0) * 1000)
            reply = resp.choices[0].message.content.strip()
            console.print(f"[green]✓[/] API call OK — {ms}ms, reply: {reply!r}")
        except Exception as exc:
            console.print(f"[red]✗[/] API call failed: {exc}")
            console.print("[dim]Check your API key and try `notegen doctor`[/]")

    console.print("\n[green]Setup complete.[/] Run: notegen <url>\n")


_ASCII_ART = """\
 ███╗   ██╗ ██████╗ ████████╗███████╗ ██████╗ ███████╗███╗   ██╗
 ████╗  ██║██╔═══██╗╚══██╔══╝██╔════╝██╔════╝ ██╔════╝████╗  ██║
 ██╔██╗ ██║██║   ██║   ██║   █████╗  ██║  ███╗█████╗  ██╔██╗ ██║
 ██║╚██╗██║██║   ██║   ██║   ██╔══╝  ██║   ██║██╔══╝  ██║╚██╗██║
 ██║ ╚████║╚██████╔╝   ██║   ███████╗╚██████╔╝███████╗██║ ╚████║
 ╚═╝  ╚═══╝ ╚═════╝    ╚═╝   ╚══════╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝\
"""


def _show_rich_help() -> None:
    from rich.console import Console
    from rich.table import Table

    ver = _get_version()
    console = Console()
    console.print(f"\n[#50C878]{_ASCII_ART}[/]")
    console.print(f"[dim]v{ver}[/]  YouTube · playlists · web pages → rich Obsidian notes\n")

    def _table(flag_col: bool = False) -> Table:
        t = Table(box=None, show_header=False, padding=(0, 2, 0, 2), expand=False)
        t.add_column(no_wrap=True, style="green" if not flag_col else "yellow")
        t.add_column(style="dim")
        return t

    console.print("[bold]FIRST-TIME SETUP[/]")
    t = _table()
    t.add_row("notegen setup", "guided wizard — choose provider, add API key, verify")
    console.print(t)

    console.print("\n[bold]COMMANDS[/]")
    t = _table()
    t.add_row("notegen <url-or-file>", "auto-detect source (YouTube, web, file)")
    t.add_row("notegen video <url>", "YouTube video → single note")
    t.add_row("notegen playlist <url>", "YouTube playlist → folder + index.md")
    t.add_row("notegen web <url>", "crawl web page → notes")
    t.add_row("notegen text <file|->", "local file or stdin")
    t.add_row("notegen auto <source>", "explicit auto-detect")
    t.add_row("notegen watch <dir>", "auto-process new .txt/.md files dropped in dir")
    console.print(t)

    console.print("\n[bold]SOURCE FLAGS[/] [dim](video · playlist · web · text · auto)[/]")
    t = _table(flag_col=True)
    t.add_row("--version", "print version and exit")
    t.add_row("-o / --output-dir PATH", "override output directory")
    t.add_row("-m / --model TEXT", "LiteLLM model  e.g. [green]groq/llama-3.3-70b-versatile[/]")
    t.add_row("-v / --verbose", "show chunk count, token usage, crawl status")
    t.add_row("--no-mermaid", "disable mermaid diagram generation")
    t.add_row("--no-cache", "skip cache read/write for this run")
    t.add_row("-n / --dry-run", "print token estimate; skip LLM call")
    t.add_row("--format TEXT", "obsidian (default) | logseq | plain | roam")
    t.add_row("--force", "skip playlist videos without captions")
    t.add_row("--force-restart", "ignore playlist resume file, reprocess all")
    t.add_row("-p / --prompt TEXT", "extra instructions appended to LLM prompt")
    console.print(t)

    console.print("\n[bold]SETUP & DIAGNOSTICS[/]")
    t = _table()
    t.add_row("notegen setup", "interactive first-run wizard")
    t.add_row("notegen doctor [--provider PROVIDER]", "config check + real API call")
    console.print(t)

    console.print("\n[bold]CONFIG[/]")
    t = _table()
    t.add_row("notegen config init", "create config file [dim](use setup instead)[/]")
    t.add_row("notegen config open", "open in default editor")
    t.add_row("notegen config show", "print resolved config")
    t.add_row("notegen config validate", "check structure + API key presence")
    console.print(t)

    console.print("\n[bold]CACHE[/]")
    t = _table()
    t.add_row("notegen cache clear", "remove all cached transcripts + notes")
    console.print(t)

    console.print("\n[bold]CONFIG FILE[/]")
    console.print("  [dim]Linux/macOS[/]  [green]~/.config/notes-gen/config.yaml[/]")
    win_path = r"%USERPROFILE%\.config\notes-gen\config.yaml"
    console.print(f"  [dim]Windows[/]     [green]{win_path}[/]")
    console.print("\n  [dim]Free providers: groq · nvidia_nim · gemini[/]")
    console.print(
        "  [dim]YouTube languages: English (direct) · Hindi · Malayalam (auto-translated)[/]\n"
    )


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
    if args == ["--version"] or args == ["-V"]:
        typer.echo(f"notegen {_get_version()}")
        return
    if args and not args[0].startswith("-") and args[0] not in _KNOWN_SUBCOMMANDS:
        sys.argv.insert(1, "auto")
    app()
