from __future__ import annotations

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table


class Dashboard:
    def __init__(self, title: str, model: str):
        self.console = Console()
        self.layout = Layout()
        self.title = title
        self.model = model

        self.overall_progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
        )
        self.overall_task = self.overall_progress.add_task("Initializing...", total=None)

        self.log_table = Table(box=None, expand=True)
        self.log_table.add_column("Time", style="dim", width=8)
        self.log_table.add_column("Message")

        self._tokens = 0
        self._cost = "$0.00"
        self.stats_table = self._make_stats_table()

        self._init_layout()
        self.live = Live(self.layout, console=self.console, refresh_per_second=4, transient=True)

    def _make_stats_table(self) -> Table:
        t = Table(box=None, expand=True)
        t.add_column("Metric", style="bold")
        t.add_column("Value", justify="right")
        t.add_row("Model", self.model)
        t.add_row("Tokens", f"{self._tokens:,}")
        t.add_row("Est. Cost", self._cost)
        return t

    def _init_layout(self):
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )
        self.layout["main"].split_row(
            Layout(name="body", ratio=3),
            Layout(name="side", ratio=1),
        )

        self.layout["header"].update(Panel(f"[bold cyan]{self.title}[/]", border_style="cyan"))
        self.layout["footer"].update(Panel(self.overall_progress, border_style="blue"))
        self.layout["body"].update(Panel(self.log_table, title="Activity", border_style="dim"))
        self.layout["side"].update(Panel(self.stats_table, title="Stats", border_style="green"))

    def log(self, message: str):
        from datetime import datetime

        time_str = datetime.now().strftime("%H:%M:%S")
        self.log_table.add_row(time_str, message)
        # Keep only last 15 logs
        if len(self.log_table.rows) > 15:
            self.log_table.rows.pop(0)

    def update_title(self, title: str) -> None:
        self.title = title
        self.layout["header"].update(Panel(f"[bold cyan]{self.title}[/]", border_style="cyan"))

    def update_stats(self, tokens: int, cost: str):
        self._tokens = tokens
        self._cost = cost
        self.stats_table = self._make_stats_table()
        self.layout["side"].update(Panel(self.stats_table, title="Stats", border_style="green"))

    def update_progress(self, completed: int, total: int, description: str | None = None):
        self.overall_progress.update(self.overall_task, completed=completed, total=total)
        if description:
            self.overall_progress.update(self.overall_task, description=description)

    def __enter__(self):
        self.live.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.live.stop()
