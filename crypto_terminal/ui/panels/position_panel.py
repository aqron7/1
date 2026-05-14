from textual.widget import Widget
from textual.reactive import reactive
from textual.app import RenderResult
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class PositionPanel(Widget):
    """Open positions with unrealized P&L."""

    positions: reactive[dict] = reactive({})
    prices: reactive[dict] = reactive({})

    DEFAULT_CSS = """
    PositionPanel {
        height: 1fr;
        border: solid $primary;
    }
    """

    def _calc_unrealized(self, pos: dict, current_price: float) -> float:
        entry = pos["entry"]
        size = pos["size"]
        if pos["side"] == "long":
            return (current_price - entry) * size
        else:
            return (entry - current_price) * size

    def render(self) -> RenderResult:
        positions = self.positions
        prices = self.prices

        if not positions:
            return Panel(
                Text("No open positions", style="dim"),
                title="[bold green]Positions[/]",
                border_style="green",
            )

        table = Table(show_header=True, header_style="bold", expand=True)
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Side", width=6)
        table.add_column("Size", justify="right")
        table.add_column("Entry", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("SL", justify="right")
        table.add_column("TP", justify="right")
        table.add_column("PnL", justify="right")

        for symbol, pos in positions.items():
            current_price = prices.get(symbol, pos["entry"])
            upnl = self._calc_unrealized(pos, current_price)
            upnl_str = f"{upnl:+.2f}"
            upnl_color = "green" if upnl >= 0 else "red"
            side_color = "green" if pos["side"] == "long" else "red"

            table.add_row(
                symbol.split("/")[0],
                f"[{side_color}]{pos['side'].upper()}[/]",
                f"{pos['size']:.4f}",
                f"{pos['entry']:.2f}",
                f"{current_price:.2f}",
                f"{pos['sl']:.2f}",
                f"{pos['tp']:.2f}",
                f"[{upnl_color}]{upnl_str}[/]",
            )

        return Panel(
            table,
            title=f"[bold green]Positions ({len(positions)})[/]",
            border_style="green",
        )

    def update_positions(self, positions: dict, prices: dict) -> None:
        self.positions = positions
        self.prices = prices
        self.refresh()
