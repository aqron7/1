from textual.widget import Widget
from textual.reactive import reactive
from textual.app import RenderResult
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class AIPanel(Widget):
    """Displays the latest Groq decision and reasoning."""

    result: reactive[dict | None] = reactive(None)
    signal_info: reactive[str] = reactive("")

    DEFAULT_CSS = """
    AIPanel {
        height: 1fr;
        border: solid $primary;
    }
    """

    def render(self) -> RenderResult:
        result = self.result

        if result is None:
            return Panel(
                Text("Waiting for AI analysis...", style="dim"),
                title="[bold magenta]AI Analysis[/]",
                border_style="magenta",
            )

        decision = result.get("decision", "unknown")
        conviction = result.get("conviction", 0)
        size_pct = result.get("size_pct", 0)
        sl = result.get("stop_loss", 0.0)
        tp = result.get("take_profit", 0.0)
        reason = result.get("reason", "")

        decision_color = {
            "execute": "bold green",
            "skip": "bold red",
            "wait": "bold yellow",
        }.get(decision, "white")

        conviction_color = "green" if conviction >= 65 else "yellow" if conviction >= 40 else "red"

        table = Table.grid(padding=(0, 1))
        table.add_column(style="dim", width=14)
        table.add_column()

        table.add_row("Decision", f"[{decision_color}]{decision.upper()}[/]")
        table.add_row("Conviction", f"[{conviction_color}]{conviction}/100[/]")
        table.add_row("Size %", f"{size_pct}%")
        table.add_row("Stop Loss", f"{sl:.4f}" if sl else "—")
        table.add_row("Take Profit", f"{tp:.4f}" if tp else "—")
        table.add_row("─" * 12, "─" * 24)
        table.add_row("Reason", Text(reason, overflow="fold"))

        if self.signal_info:
            table.add_row("─" * 12, "─" * 24)
            table.add_row("Signal", Text(self.signal_info, style="dim", overflow="fold"))

        return Panel(
            table,
            title="[bold magenta]AI Analysis — Groq[/]",
            border_style="magenta",
        )

    def update_result(self, result: dict, signal_info: str = "") -> None:
        self.result = result
        self.signal_info = signal_info
        self.refresh()
