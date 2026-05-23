from __future__ import annotations

from dataclasses import dataclass, replace
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

    def __post_init__(self) -> None:
        if self.output_dir is None:
            self.output_dir = Path.home() / "notes"
        self.output_dir = Path(self.output_dir)


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    if not path.exists():
        return Config()
    raw = yaml.safe_load(path.read_text()) or {}
    kwargs: dict = {}
    if "output_dir" in raw:
        kwargs["output_dir"] = Path(raw["output_dir"])
    for field in ("model", "mermaid", "max_concurrent", "web_max_pages", "web_max_depth"):
        if field in raw:
            kwargs[field] = raw[field]
    return Config(**kwargs)


def merge_cli_overrides(
    cfg: Config,
    *,
    output_dir: Optional[Path] = None,
    model: Optional[str] = None,
    mermaid: Optional[bool] = None,
) -> Config:
    overrides: dict = {}
    if output_dir is not None:
        overrides["output_dir"] = output_dir
    if model is not None:
        overrides["model"] = model
    if mermaid is not None:
        overrides["mermaid"] = mermaid
    return replace(cfg, **overrides)
