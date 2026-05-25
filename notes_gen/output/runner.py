from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

from loguru import logger

from notes_gen.config import Config
from notes_gen.output.dashboard import Dashboard

_current_dashboard: Optional[Dashboard] = None

@contextmanager
def use_dashboard(title: str, cfg: Config) -> Generator[Dashboard, None, None]:
    """Provides a dashboard if we are not in dry-run or verbose mode."""
    global _current_dashboard
    if cfg.dry_run or cfg.verbose:
        # In dry-run or verbose mode, we don't want the live dashboard 
        # as it might interfere with normal output or progress bars.
        yield None # type: ignore
        return

    with Dashboard(title, cfg.model) as db:
        _current_dashboard = db
        try:
            yield db
        finally:
            _current_dashboard = None

def get_dashboard() -> Optional[Dashboard]:
    """Get the currently active dashboard."""
    return _current_dashboard

def log_to_dashboard(message: str):
    """Log to the active dashboard if it exists, otherwise just log to loguru."""
    logger.info(message)
    if _current_dashboard:
        _current_dashboard.log(message)

def update_dashboard_stats(tokens: int, cost: str):
    """Update stats on the active dashboard if it exists."""
    if _current_dashboard:
        _current_dashboard.update_stats(tokens, cost)

def update_dashboard_progress(completed: int, total: int, description: str | None = None):
    """Update progress on the active dashboard if it exists."""
    if _current_dashboard:
        _current_dashboard.update_progress(completed, total, description)
