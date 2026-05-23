from pathlib import Path
from typing import Optional

import typer
import yaml

from notes_gen.config import (
    CONFIG_TEMPLATE,
    DEFAULT_CONFIG_PATH,
    Config,
    load_config,
    merge_cli_overrides,
)

app = typer.Typer(no_args_is_help=True, help="Convert YouTube/web content to Obsidian notes.")
config_app = typer.Typer(help="Manage configuration.")
app.add_typer(config_app, name="config")

_KNOWN_SUBCOMMANDS = {"video", "playlist", "web", "text", "config", "auto"}


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


@config_app.command("init")
def config_init() -> None:
    """Create default config at ~/.config/notes-gen/config.yaml."""
    if DEFAULT_CONFIG_PATH.exists():
        typer.echo(f"Config already exists: {DEFAULT_CONFIG_PATH}")
        raise typer.Exit(1)
    DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_CONFIG_PATH.write_text(CONFIG_TEMPLATE)
    typer.echo(f"Config written to {DEFAULT_CONFIG_PATH}")


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
    }
    typer.echo(yaml.dump(data, default_flow_style=False), nl=False)


@app.command()
def video(
    url: str = typer.Argument(..., help="YouTube video URL"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    no_mermaid: bool = typer.Option(False, "--no-mermaid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Generate notes from a YouTube video."""
    from notes_gen.sources.youtube import run_video_pipeline

    cfg = load_config()
    cfg = merge_cli_overrides(cfg, output_dir=output_dir, model=model, mermaid=not no_mermaid)
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
) -> None:
    """Generate notes from a YouTube playlist."""
    from notes_gen.sources.youtube import run_playlist_pipeline

    cfg = load_config()
    cfg = merge_cli_overrides(cfg, output_dir=output_dir, model=model, mermaid=not no_mermaid)
    index_path = run_playlist_pipeline(url, cfg, force=force)
    typer.echo(f"Playlist notes written to {index_path.parent}")


@app.command()
def web(
    url: str = typer.Argument(..., help="Web URL to fetch"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    no_mermaid: bool = typer.Option(False, "--no-mermaid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Generate notes from a web page (crawls same-domain links)."""
    from notes_gen.sources.web import run_web_crawl_pipeline

    cfg = load_config()
    cfg = merge_cli_overrides(cfg, output_dir=output_dir, model=model, mermaid=not no_mermaid)
    output_path = run_web_crawl_pipeline(url, cfg)
    typer.echo(f"Notes written to {output_path}")


@app.command()
def text(
    source: str = typer.Argument(..., help="File path or '-' for stdin"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    no_mermaid: bool = typer.Option(False, "--no-mermaid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Generate notes from a text file or stdin."""
    from notes_gen.sources.text import run_text_pipeline

    cfg = load_config()
    cfg = merge_cli_overrides(cfg, output_dir=output_dir, model=model, mermaid=not no_mermaid)
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
) -> None:
    """Auto-detect source type and generate notes."""
    cfg = load_config()
    cfg = merge_cli_overrides(cfg, output_dir=output_dir, model=model, mermaid=not no_mermaid)
    _run_auto(source, cfg, force=force)


def main() -> None:
    """Entry point: inject 'auto' subcommand when bare URL/file is passed."""
    import sys

    args = sys.argv[1:]
    if args and not args[0].startswith("-") and args[0] not in _KNOWN_SUBCOMMANDS:
        sys.argv.insert(1, "auto")
    app()
