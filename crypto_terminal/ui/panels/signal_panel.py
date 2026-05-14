from textual.widget import Widget
from textual.reactive import reactive
from textual.app import RenderResult
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from strategy.scorer import SignalEvent


class SignalPanel(Widget):
    """Live signal feed: latest indicator values, score, and strategy tag."""

    signal: reactive[SignalEvent | None] = reactive(None)

    DEFAULT_CSS = """
    SignalPanel {
        height: 1fr;
        border: solid $primary;
    }
    """

    def render(self) -> RenderResult:
        sig = self.signal

        if sig is None:
            return Panel(
                Text("No signals yet...", style="dim"),
                title="[bold yellow]Signals[/]",
                border_style="yellow",
            )

        side_color = "green" if sig.side == "long" else "red"
        score_color = "green" if sig.score >= 75 else "yellow" if sig.score >= 60 else "red"

        table = Table.grid(padding=(0, 1))
        table.add_column(style="dim", width=16)
        table.add_column()

        table.add_row("Symbol", f"[bold]{sig.symbol}[/]")
        table.add_row("Timeframe", sig.timeframe)
        table.add_row("Side", f"[{side_color}]{sig.side.upper()}[/]")
        table.add_row("Score", f"[{score_color}]{sig.score}/100[/]")
        table.add_row("Strategy", f"[cyan]{sig.strategy_tag}[/]")
        table.add_row("Regime", sig.regime)
        table.add_row("Close", f"{sig.close:.4f}")
        table.add_row("ATR", f"{sig.atr:.4f}")
        table.add_row("─" * 14, "─" * 20)
        table.add_row("RSI", f"{sig.indicators['rsi']:.1f}")
        table.add_row("EMA spread", f"{sig.indicators['ema_spread']:.3f}%")
        table.add_row("Vol ratio", f"{sig.indicators['vol_ratio']:.2f}x")
        table.add_row("BB position", f"{sig.indicators['bb_pct']:.2f}")
        table.add_row("OBV slope", sig.indicators["obv_slope"])

        return Panel(
            table,
            title="[bold yellow]Latest Signal[/]",
            border_style="yellow",
        )

    def update_signal(self, signal: SignalEvent) -> None:
        self.signal = signal
        self.refresh()
