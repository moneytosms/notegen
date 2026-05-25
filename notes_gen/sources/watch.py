from __future__ import annotations

import json
from pathlib import Path

from loguru import logger
from watchfiles import watch

from notes_gen.config import Config

_STATE_FILE = ".watch-state.json"
_WATCH_EXTENSIONS = {".txt", ".md"}


def _load_state(watch_dir: Path) -> set[str]:
    state_path = watch_dir / _STATE_FILE
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            return set(data.get("processed", []))
        except Exception:
            return set()
    return set()


def _save_state(watch_dir: Path, processed: set[str]) -> None:
    state_path = watch_dir / _STATE_FILE
    state_path.write_text(json.dumps({"processed": sorted(processed)}), encoding="utf-8")


def _process_file(path: Path, cfg: Config) -> bool:
    from notes_gen.sources.text import run_text_pipeline

    try:
        output = run_text_pipeline(str(path), cfg)
        logger.info(f"Processed: {path.name} → {output.name}")
        return True
    except Exception as exc:
        logger.error(f"Failed to process {path.name}: {exc}")
        return False


def run_watch(watch_dir: Path, cfg: Config) -> None:
    processed = _load_state(watch_dir)
    logger.info(f"Monitoring directory: {watch_dir}")
    logger.info("Press Ctrl+C to stop.")

    # process any existing unprocessed files first
    for path in sorted(watch_dir.iterdir()):
        if (
            path.suffix in _WATCH_EXTENSIONS
            and path.name != _STATE_FILE
            and str(path) not in processed
        ):
            if _process_file(path, cfg):
                processed.add(str(path))
                _save_state(watch_dir, processed)

    try:
        for changes in watch(str(watch_dir), watch_filter=_change_filter):
            for _, changed_path in changes:
                path = Path(changed_path)
                if (
                    path.suffix in _WATCH_EXTENSIONS
                    and path.name != _STATE_FILE
                    and str(path) not in processed
                    and path.exists()
                ):
                    if _process_file(path, cfg):
                        processed.add(str(path))
                        _save_state(watch_dir, processed)
    except KeyboardInterrupt:
        logger.info("Watch stopped.")


def _change_filter(change, path: str) -> bool:
    return Path(path).suffix in _WATCH_EXTENSIONS and Path(path).name != _STATE_FILE
