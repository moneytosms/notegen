import logging
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any, cast

import litellm
import typer
import yaml
from loguru import logger

from notes_gen.config import (
    CONFIG_TEMPLATE,
    DEFAULT_CONFIG_PATH,
    Config,
    load_config,
    merge_cli_overrides,
)
from notes_gen.logger import setup_logger

logging.getLogger("LiteLLM").setLevel(logging.ERROR)

app = typer.Typer(no_args_is_help=False, help="Convert YouTube/web content to Obsidian notes.")
config_app = typer.Typer(help="Manage configuration.")
cache_app = typer.Typer(help="Manage local cache.")
app.add_typer(config_app, name="config")
app.add_typer(cache_app, name="cache")


@cache_app.command("clear")
def cache_clear() -> None:
    """Delete all cached notes and transcripts."""
    from notes_gen.cache import clear_cache

    count = clear_cache()
    typer.echo(f"Cleared {count} cache file(s).")


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
    "interactive",
}


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


def _export_note(path: Path, fmt: str) -> None:
    import pypandoc

    out_path = path.with_suffix(f".{fmt}")
    logger.info(f"Exporting {path.name} to {fmt}...")
    try:
        # Check if pandoc is available
        try:
            pypandoc.get_pandoc_version()
        except OSError:
            logger.error("Pandoc not found on system. Please install pandoc to use --export.")
            return

        pypandoc.convert_file(str(path), fmt, outputfile=str(out_path))
        logger.info(f"Exported: {out_path}")
    except Exception as e:
        logger.error(f"Failed to export {fmt}: {e}")


def _run_auto(
    source: str,
    cfg: Config,
    force: bool = False,
    force_restart: bool = False,
    export: str | None = None,
) -> None:
    path: Path | None = None
    if "youtube.com/playlist" in source or ("list=" in source and "youtube.com" in source):
        from notes_gen.sources.youtube import run_playlist_pipeline

        path = run_playlist_pipeline(source, cfg, force=force, force_restart=force_restart)
    elif "youtube.com/watch" in source or "youtu.be/" in source:
        from notes_gen.sources.youtube import run_video_pipeline

        path = run_video_pipeline(source, cfg)
    elif source.startswith("http://") or source.startswith("https://"):
        from notes_gen.sources.web import run_web_crawl_pipeline

        path = run_web_crawl_pipeline(source, cfg)
    else:
        from notes_gen.sources.text import run_text_pipeline

        path = run_text_pipeline(source, cfg)

    if export and path:
        _export_note(path, export)


def version_callback(value: bool):
    if value:
        typer.echo(f"notegen {_get_version()}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool | None = typer.Option(
        None, "--version", callback=version_callback, is_eager=True, help="Show version and exit"
    ),
):
    pass


@app.command()
def video(
    url: str = typer.Argument(..., help="YouTube video URL"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o"),
    model: str | None = typer.Option(None, "--model", "-m"),
    no_mermaid: bool = typer.Option(False, "--no-mermaid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    force: bool = typer.Option(False, "--force"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Print estimate; skip LLM"),
    fmt: str | None = typer.Option(None, "--format", help="obsidian|logseq|plain|roam"),
    lang: str | None = typer.Option(None, "--lang", help="Target language code (e.g. en, es)"),
    template: str | None = typer.Option(None, "--template", "-t", help="Named prompt template"),
    export: str | None = typer.Option(None, "--export", help="pdf|html|docx"),
    toc: bool = typer.Option(False, "--toc", help="Insert table of contents"),
    prompt: str | None = typer.Option(
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
        language=lang,
        template=template,
        toc=toc or None,
    )
    setup_logger(cfg.verbose)
    logger.info(f"Generating notes for video: {url}")
    path = run_video_pipeline(url, cfg)
    if export:
        _export_note(path, export)


@app.command()
def playlist(
    url: str = typer.Argument(..., help="YouTube playlist URL"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o"),
    model: str | None = typer.Option(None, "--model", "-m"),
    no_mermaid: bool = typer.Option(False, "--no-mermaid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    force: bool = typer.Option(False, "--force"),
    force_restart: bool = typer.Option(False, "--force-restart", help="Ignore progress file"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Print estimate; skip LLM"),
    fmt: str | None = typer.Option(None, "--format", help="obsidian|logseq|plain|roam"),
    lang: str | None = typer.Option(None, "--lang", help="Target language code (e.g. en, es)"),
    incremental: bool | None = typer.Option(
        None, "--incremental/--no-incremental", help="Skip existing files"
    ),
    template: str | None = typer.Option(None, "--template", "-t", help="Named prompt template"),
    export: str | None = typer.Option(None, "--export", help="pdf|html|docx"),
    toc: bool = typer.Option(False, "--toc", help="Insert table of contents"),
    prompt: str | None = typer.Option(
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
        language=lang,
        incremental=incremental,
        template=template,
        toc=toc or None,
    )
    setup_logger(cfg.verbose)
    logger.info(f"Generating notes for playlist: {url}")
    index_path = run_playlist_pipeline(url, cfg, force=force, force_restart=force_restart)
    if export:
        _export_note(index_path, export)


@app.command()
def web(
    url: str = typer.Argument(..., help="Web URL to fetch"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o"),
    model: str | None = typer.Option(None, "--model", "-m"),
    no_mermaid: bool = typer.Option(False, "--no-mermaid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Print estimate; skip LLM"),
    fmt: str | None = typer.Option(None, "--format", help="obsidian|logseq|plain|roam"),
    lang: str | None = typer.Option(None, "--lang", help="Target language code (e.g. en, es)"),
    template: str | None = typer.Option(None, "--template", "-t", help="Named prompt template"),
    export: str | None = typer.Option(None, "--export", help="pdf|html|docx"),
    toc: bool = typer.Option(False, "--toc", help="Insert table of contents"),
    prompt: str | None = typer.Option(
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
        language=lang,
        template=template,
        toc=toc or None,
    )
    setup_logger(cfg.verbose)
    logger.info(f"Generating notes for web URL: {url}")
    path = run_web_crawl_pipeline(url, cfg)
    if export:
        _export_note(path, export)


@app.command()
def text(
    source: str = typer.Argument(..., help="File path or '-' for stdin"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o"),
    model: str | None = typer.Option(None, "--model", "-m"),
    no_mermaid: bool = typer.Option(False, "--no-mermaid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Print estimate; skip LLM"),
    fmt: str | None = typer.Option(None, "--format", help="obsidian|logseq|plain|roam"),
    lang: str | None = typer.Option(None, "--lang", help="Target language code (e.g. en, es)"),
    template: str | None = typer.Option(None, "--template", "-t", help="Named prompt template"),
    export: str | None = typer.Option(None, "--export", help="pdf|html|docx"),
    toc: bool = typer.Option(False, "--toc", help="Insert table of contents"),
    prompt: str | None = typer.Option(
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
        language=lang,
        template=template,
        toc=toc or None,
    )
    setup_logger(cfg.verbose)
    logger.info(f"Generating notes from text: {source}")
    path = run_text_pipeline(source, cfg)
    if export:
        _export_note(path, export)


@app.command()
def auto(
    source: str = typer.Argument(..., help="YouTube URL, web URL, or file path"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o"),
    model: str | None = typer.Option(None, "--model", "-m"),
    no_mermaid: bool = typer.Option(False, "--no-mermaid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    force: bool = typer.Option(False, "--force"),
    force_restart: bool = typer.Option(False, "--force-restart", help="Ignore progress file"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Print estimate; skip LLM"),
    fmt: str | None = typer.Option(None, "--format", help="obsidian|logseq|plain|roam"),
    lang: str | None = typer.Option(None, "--lang", help="Target language code (e.g. en, es)"),
    incremental: bool | None = typer.Option(
        None, "--incremental/--no-incremental", help="Skip existing files"
    ),
    template: str | None = typer.Option(None, "--template", "-t", help="Named prompt template"),
    export: str | None = typer.Option(None, "--export", help="pdf|html|docx"),
    toc: bool = typer.Option(False, "--toc", help="Insert table of contents"),
    prompt: str | None = typer.Option(
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
        language=lang,
        incremental=incremental,
        template=template,
        toc=toc or None,
    )
    setup_logger(cfg.verbose)
    logger.info(f"Auto-detecting source and generating notes: {source}")
    _run_auto(source, cfg, force=force, force_restart=force_restart, export=export)


@app.command()
def watch(
    directory: Path = typer.Argument(..., help="Directory to watch for new .txt/.md files"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o"),
    model: str | None = typer.Option(None, "--model", "-m"),
    no_mermaid: bool = typer.Option(False, "--no-mermaid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    fmt: str | None = typer.Option(None, "--format", help="obsidian|logseq|plain|roam"),
    lang: str | None = typer.Option(None, "--lang", help="Target language code (e.g. en, es)"),
    template: str | None = typer.Option(None, "--template", "-t", help="Named prompt template"),
    prompt: str | None = typer.Option(
        None, "--prompt", "-p", help="Extra instructions for LLM prompt"
    ),
) -> None:
    """Watch a directory and generate notes for every new text file."""
    from notes_gen.sources.watch import run_watch

    cfg = load_config()
    cfg = merge_cli_overrides(
        cfg,
        output_dir=output_dir,
        model=model,
        mermaid=not no_mermaid,
        verbose=verbose,
        cache=not no_cache,
        output_format=fmt,
        extra_prompt=prompt,
        language=lang,
        template=template,
    )
    setup_logger(cfg.verbose)
    run_watch(directory, cfg)


@app.command("interactive")
def interactive_mode() -> None:
    """Interactive guided mode — generate notes through prompts."""
    from rich.console import Console
    from rich.prompt import Confirm, Prompt

    console = Console()
    console.print("\n[bold cyan]notegen interactive[/] — guided note generation\n")

    cfg = load_config()

    # 1. Source
    source = Prompt.ask("Enter source (YouTube URL, Web URL, or file path)")

    # 2. Basic detection for better defaults
    is_playlist = "youtube.com/playlist" in source or "list=" in source

    # 3. Model
    console.print(f"\nModel [dim](default: {cfg.model})[/]")
    model = Prompt.ask("Change model?", default=cfg.model)

    # 4. Language
    lang = Prompt.ask("Target language code", default=cfg.language)

    # 5. Templates
    template = None
    if cfg.prompt_templates:
        console.print("\n[bold]Available templates:[/]")
        tpl_keys = list(cfg.prompt_templates.keys())
        for i, k in enumerate(tpl_keys, 1):
            console.print(f"  [green]{i:2}[/] {k}")

        tpl_choice = Prompt.ask(
            "Select a template (number or name)", choices=["none"] + tpl_keys, default="none"
        )
        if tpl_choice != "none":
            if tpl_choice.isdigit() and 1 <= int(tpl_choice) <= len(tpl_keys):
                template = tpl_keys[int(tpl_choice) - 1]
            else:
                template = tpl_choice

    # 6. Advanced options
    incremental = cfg.incremental
    if is_playlist:
        incremental = Confirm.ask("Skip videos if notes already exist?", default=cfg.incremental)

    dry_run = Confirm.ask("Dry run? (estimate only, no LLM calls)", default=False)

    export = Prompt.ask(
        "Export format (none|pdf|html)", choices=["none", "pdf", "html"], default="none"
    )
    if export == "none":
        export = None

    # 7. Apply overrides
    cfg = merge_cli_overrides(
        cfg,
        model=model,
        language=lang,
        incremental=incremental,
        dry_run=dry_run or None,
        template=template,
    )
    setup_logger(cfg.verbose)
    logger.info("Starting interactive note generation")

    console.print("\n[bold green]Configuration complete. Starting pipeline...[/]\n")
    _run_auto(source, cfg, export=export)


@app.command()
def setup() -> None:
    """Interactive guided setup wizard — configure provider, model, API keys."""
    from rich.console import Console

    console = Console()
    console.print("\n[bold cyan]notegen setup[/] — guided configuration\n")

    # Load existing config for defaults
    current_raw: dict[str, Any] = {}
    if DEFAULT_CONFIG_PATH.exists():
        try:
            current_raw = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        except Exception:
            pass

    # Step 1: Choose provider
    current_model = current_raw.get("model", "")
    current_provider = current_model.split("/")[0] if "/" in current_model else "groq"

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

    console.print("[bold]Available providers:[/]")
    for i, (prov, label) in enumerate(_PROVIDER_LIST, 1):
        console.print(f"  [green]{i:2}[/] {prov:<15} [dim]{label}[/]")

    console.print(f"\nChoose provider [Enter = {current_provider}]: ", end="")
    choice = input().strip()
    if not choice:
        provider = current_provider
    elif choice.isdigit() and 1 <= int(choice) <= len(_PROVIDER_LIST):
        provider = _PROVIDER_LIST[int(choice) - 1][0]
    else:
        provider = choice

    # Step 2: Choose model
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
    default_model = (
        current_model
        if current_model and current_model.startswith(provider)
        else _PROVIDER_TEST_MODELS.get(provider, f"{provider}/unknown")
    )
    console.print(f"\nModel [Enter = {default_model}]: ", end="")
    model_input = input().strip()
    model = model_input if model_input else default_model

    # Step 3: Output directory
    current_out = current_raw.get("output_dir", "~/notes")
    console.print(f"\nOutput directory [Enter = {current_out}]: ", end="")
    output_dir = input().strip() or current_out

    # Step 4: API keys
    all_new_keys: list[str] = []
    if provider != "ollama":
        console.print(f"\nPaste API key(s) for [bold]{provider}[/] (blank line to stop):")
        while True:
            console.print("  key: ", end="")
            k = input().strip()
            if not k:
                break
            if "XXXX" in k or "<your" in k:
                console.print("  [yellow]Skipped — looks like a placeholder[/]")
                continue
            all_new_keys.append(k)
            console.print("  [green]✓[/] added")

    # Step 5: Additional providers
    extra_providers: list[tuple[str, list[str]]] = []
    console.print("\nAdd keys for another provider? [y/N]: ", end="")
    if input().strip().lower() == "y":
        while True:
            console.print("Provider name (blank to stop): ", end="")
            extra_prov = input().strip().lower()
            if not extra_prov:
                break
            prov_keys = []
            console.print(f"Keys for {extra_prov} (blank to stop):")
            while True:
                console.print("  key: ", end="")
                k = input().strip()
                if not k:
                    break
                prov_keys.append(k)
                console.print("  [green]✓[/] added")
            if prov_keys:
                extra_providers.append((extra_prov, prov_keys))

    # Step 6: Write config
    action = "updated" if DEFAULT_CONFIG_PATH.exists() else "created"
    _merge_config(DEFAULT_CONFIG_PATH, provider, all_new_keys, model, output_dir)
    for ep, ek in extra_providers:
        _merge_config(DEFAULT_CONFIG_PATH, ep, ek)

    console.print(f"\n[green]✓[/] Config {action}: {DEFAULT_CONFIG_PATH}")

    # Step 7: Run doctor
    console.print("\nRun doctor to verify connection? [Y/n]: ", end="")
    if input().strip().lower() != "n":
        try:
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
            resp = cast(Any, litellm.completion(**kwargs))
            ms = int((time.monotonic() - t0) * 1000)
            reply = cast(str, resp.choices[0].message.content).strip()
            console.print(f"[green]✓[/] API call OK — {ms}ms, reply: {reply!r}")
        except Exception as exc:
            console.print(f"[red]✗[/] API call failed: {exc}")
            console.print("[dim]Check your API key and try `notegen doctor`[/]")

    console.print("\n[green]Setup complete.[/] Run: notegen <url>\n")


def _merge_config(
    path: Path, provider: str, new_keys: list[str], model: str = "", output_dir: str = ""
) -> None:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.exists() else {}

    if model:
        raw["model"] = model
    if output_dir:
        raw["output_dir"] = output_dir

    if not isinstance(raw.get("api_keys"), dict):
        raw["api_keys"] = {}
    if not isinstance(raw["api_keys"].get(provider), list):
        raw["api_keys"][provider] = []

    existing = set(raw["api_keys"][provider])
    raw["api_keys"][provider].extend(k for k in new_keys if k and k not in existing)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True), encoding="utf-8")


@config_app.command("init")
def config_init() -> None:
    """Create a default configuration file at ~/.config/notes-gen/config.yaml."""
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
    """Open the configuration file in your default editor."""
    if not DEFAULT_CONFIG_PATH.exists():
        config_init()
        typer.echo(f"Config created: {DEFAULT_CONFIG_PATH}")
    typer.echo(f"Opening {DEFAULT_CONFIG_PATH}")
    if platform.system() == "Windows":
        os.startfile(DEFAULT_CONFIG_PATH)
    elif platform.system() == "Darwin":
        subprocess.run(["open", str(DEFAULT_CONFIG_PATH)])
    else:
        subprocess.run(["xdg-open", str(DEFAULT_CONFIG_PATH)])


@config_app.command("validate")
def config_validate() -> None:
    """Check config for errors and show stats."""
    from rich.console import Console

    console = Console()
    errors = []

    def _pass(msg: str):
        console.print(f"  [green]✓[/] {msg}")

    def _fail(msg: str):
        console.print(f"  [red]✗[/] {msg}")
        errors.append(msg)

    console.print("\n[bold]notegen config validate[/]\n")

    if not DEFAULT_CONFIG_PATH.exists():
        _fail(f"Config file not found: {DEFAULT_CONFIG_PATH}")
    else:
        try:
            cfg = load_config()
            _pass("Config file loaded")
            _pass(f"Active model: {cfg.model}")
            _pass(f"Output directory: {cfg.output_dir}")

            # Check keys
            providers = [p for p, keys in cfg.api_keys.items() if keys]
            if providers:
                _pass(f"Configured providers: {', '.join(providers)}")
            else:
                _fail("No API keys found in config")

        except Exception as e:
            _fail(f"Error parsing config: {e}")

    console.print()
    if not errors:
        console.print("[green]Config is valid.[/]\n")
    else:
        console.print("[red]Config has issues — fix them before running notegen.[/]\n")
        raise typer.Exit(1)


@config_app.command("show")
def config_show() -> None:
    """Print the current configuration (hides API keys)."""
    cfg = load_config()
    # Convert to dict and stringify paths for YAML
    data = cfg.model_dump()
    data["output_dir"] = str(data["output_dir"])

    if "api_keys" in data:
        for provider in data["api_keys"]:
            data["api_keys"][provider] = [
                f"{k[:4]}...{k[-4:]}" if len(k) > 8 else "***" for k in data["api_keys"][provider]
            ]
    typer.echo(yaml.dump(data, default_flow_style=False), nl=False)


@app.command()
def doctor() -> None:
    """Diagnose your environment and LLM connectivity."""
    from rich.console import Console

    console = Console()
    errors = []

    def _pass(msg: str):
        console.print(f"  [green]✓[/] {msg}")

    def _fail(msg: str):
        console.print(f"  [red]✗[/] {msg}")
        errors.append(msg)

    console.print("\n[bold]notegen doctor[/]\n")

    # 1. Environment
    _pass(f"OS: {platform.system()} {platform.release()}")
    _pass(f"Python: {platform.python_version()}")
    _pass(f"Version: {_get_version()}")

    # 2. Config
    cfg = Config()
    if not DEFAULT_CONFIG_PATH.exists():
        _fail("Config file missing. Run `notegen config init`.")
    else:
        try:
            cfg = load_config()
            _pass("Config file found")
        except Exception as e:
            _fail(f"Config error: {e}")

    # 3. Connection
    try:
        import httpx

        with httpx.Client(timeout=5) as client:
            client.get("https://google.com")
        _pass("Internet connection OK")
    except Exception:
        _fail("No internet connection")

    if errors:
        console.print("\n[red]Config issues found — fix before continuing.[/]\n")
        raise typer.Exit(1)

    console.print(f"\n[dim]Sending test request to {cfg.model}...[/]")
    api_key = cfg.pick_api_key()
    masked = f"{api_key[:6]}...{api_key[-4:]}" if api_key else None

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

        resp = cast(Any, litellm.completion(**kwargs))
        latency_ms = int((time.monotonic() - t0) * 1000)
        reply = cast(str, resp.choices[0].message.content).strip()
    except Exception as exc:
        _fail(f"API call failed: {exc}")
        console.print("\n[red]Doctor found issues.[/]\n")
        raise typer.Exit(1)

    _pass(f"API call succeeded — latency {latency_ms}ms, reply: {reply!r}")
    if masked:
        _pass(f"Key used: {masked}")
    console.print("\n[green]Doctor OK — notegen is ready.[/]\n")
    raise typer.Exit(0)


def main() -> None:
    import sys

    # Typer help customization
    if len(sys.argv) == 1 or sys.argv[1] in ("--help", "-h"):
        _show_custom_help()
        return

    # Check for legacy source mapping
    if len(sys.argv) > 1 and sys.argv[1] not in _KNOWN_SUBCOMMANDS:
        # If the first arg is not a command, it's likely a URL/source for 'auto'
        sys.argv.insert(1, "auto")

    app()


_ASCII_ART = r"""
 ███╗   ██╗ ██████╗ ████████╗███████╗ ██████╗ ███████╗███╗   ██╗
 ████╗  ██║██╔═══██╗╚══██╔══╝██╔════╝██╔════╝ ██╔════╝████╗  ██║
 ██╔██╗ ██║██║   ██║   ██║   █████╗  ██║  ███╗█████╗  ██╔██╗ ██║
 ██║╚██╗██║██║   ██║   ██║   ██╔══╝  ██║   ██║██╔══╝  ██║╚██╗██║
 ██║ ╚████║╚██████╔╝   ██║   ███████╗╚██████╔╝███████╗██║ ╚████║
 ╚═╝  ╚═══╝ ╚═════╝    ╚═╝   ╚══════╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝"""


def _show_custom_help():
    from rich.console import Console
    from rich.table import Table

    console = Console()
    ver = _get_version()

    win_path = r"%USERPROFILE%\.config\notes-gen\config.yaml"

    console.print(f"\n[#50C878]{_ASCII_ART}[/]")
    console.print(f"  [dim]v{ver}[/]  YouTube · playlists · web pages → Obsidian notes\n")

    console.print("[bold]COMMANDS[/]")
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_row("notegen [cyan]<url>[/]", "[dim]Auto-detect source and generate notes[/]")
    t.add_row("notegen [cyan]video <url>[/]", "[dim]YouTube video[/]")
    t.add_row("notegen [cyan]playlist <url>[/]", "[dim]YouTube playlist[/]")
    t.add_row("notegen [cyan]web <url>[/]", "[dim]Web page or site crawl[/]")
    t.add_row("notegen [cyan]text <file|->[/]", "[dim]Text file or stdin[/]")
    t.add_row("notegen [cyan]interactive[/]", "[dim]Guided wizard[/]")
    t.add_row("notegen [cyan]watch <dir>[/]", "[dim]Monitor folder for new files[/]")
    console.print(t)

    console.print("\n[bold]FLAGS[/] [dim](video · playlist · web · text · auto)[/]")
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_row("-o, --output-dir [cyan]<path>[/]", "[dim]Override output directory[/]")
    t.add_row("-m, --model [cyan]<str>[/]", "[dim]LiteLLM model string[/]")
    t.add_row("-n, --dry-run", "[dim]Estimate cost, skip LLM calls[/]")
    t.add_row("-v, --verbose", "[dim]Show detailed logs[/]")
    t.add_row("--lang [cyan]<code>[/]", "[dim]Target language, e.g. en, es, hi[/]")
    t.add_row("-t, --template [cyan]<name>[/]", "[dim]Apply named prompt style from config[/]")
    t.add_row("--export [cyan]<fmt>[/]", "[dim]Export to pdf | html | docx[/]")
    t.add_row("--toc", "[dim]Insert table of contents[/]")
    t.add_row("--no-cache", "[dim]Skip cache read and write[/]")
    console.print(t)

    console.print("\n[bold]SETUP & DIAGNOSTICS[/]")
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_row("notegen [cyan]setup[/]", "[dim]Interactive first-run configuration[/]")
    t.add_row("notegen [cyan]doctor[/]", "[dim]Check environment and LLM connectivity[/]")
    console.print(t)

    console.print("\n[bold]CONFIG[/]")
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_row("notegen [cyan]config init[/]", "[dim]Create default config file[/]")
    t.add_row("notegen [cyan]config open[/]", "[dim]Open config in editor[/]")
    t.add_row("notegen [cyan]config show[/]", "[dim]Print current settings (keys masked)[/]")
    t.add_row("notegen [cyan]config validate[/]", "[dim]Validate config and report errors[/]")
    t.add_row("notegen [cyan]cache clear[/]", "[dim]Delete all local cache entries[/]")
    console.print(t)

    console.print("\n[bold]CONFIG FILE[/]")
    console.print("  [dim]Linux / macOS[/]  [green]~/.config/notes-gen/config.yaml[/]")
    console.print(f"  [dim]Windows[/]       [green]{win_path}[/]")
    console.print("\n  [dim]Free providers: groq · nvidia_nim · gemini[/]")
    console.print("\n  [italic dim]Docs: https://github.com/moneytosms/notegen[/]\n")


if __name__ == "__main__":
    main()
