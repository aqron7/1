from textual.widget import Widget
from textual.reactive import reactive
from textual.app import RenderResult
from rich.panel import Panel
from rich.text import Text


class LogPanel(Widget):
    """Scrolling event log panel — trade log + system events."""

    events: reactive[list[str]] = reactive([])

    DEFAULT_CSS = """
    LogPanel {
        height: 1fr;
        border: solid $primary;
    }
    """

    def render(self) -> RenderResult:
        events = self.events

        if not events:
            return Panel(
                Text("No events yet...", style="dim"),
                title="[bold white]Event Log[/]",
                border_style="white",
            )

        height = self.size.height or 10
        visible_lines = max(height - 4, 3)
        recent = events[-visible_lines:]

        lines = []
        for event in reversed(recent):
            if "[GROQ ERROR]" in event or "[ORDER ERROR]" in event or "ERROR" in event:
                lines.append(f"[red]{event}[/]")
            elif "TP hit" in event or "pnl=+" in event:
                lines.append(f"[green]{event}[/]")
            elif "SL hit" in event or "pnl=-" in event:
                lines.append(f"[red]{event}[/]")
            elif "[PAPER]" in event or "[LIVE]" in event:
                lines.append(f"[cyan]{event}[/]")
            elif "[GROQ]" in event:
                lines.append(f"[magenta]{event}[/]")
            elif "[CLOSE]" in event:
                lines.append(f"[yellow]{event}[/]")
            else:
                lines.append(f"[dim]{event}[/]")

        content = Text.from_markup("\n".join(lines))
        return Panel(
            content,
            title=f"[bold white]Event Log ({len(events)} total)[/]",
            border_style="white",
        )

    def update_events(self, events: list[str]) -> None:
        self.events = list(events)
        self.refresh()
