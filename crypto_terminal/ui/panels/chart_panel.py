from textual.widget import Widget
from textual.reactive import reactive
from textual.app import RenderResult
from rich.text import Text
from rich.panel import Panel
import pandas as pd


class ChartPanel(Widget):
    """ASCII price chart with EMA_9/EMA_21 overlay. Shows last 60 bars."""

    symbol: reactive[str] = reactive("BTC/USDC:USDC")
    df: reactive[pd.DataFrame | None] = reactive(None)

    DEFAULT_CSS = """
    ChartPanel {
        height: 1fr;
        border: solid $primary;
    }
    """

    def _build_chart(self, df: pd.DataFrame, width: int, height: int) -> list[str]:
        n_bars = min(60, len(df))
        df_slice = df.tail(n_bars).reset_index(drop=True)

        closes = df_slice["close"].tolist()
        ema_fast_col = next((c for c in df.columns if c.startswith("EMA_9")), None)
        ema_slow_col = next((c for c in df.columns if c.startswith("EMA_21")), None)
        ema_fast = df_slice[ema_fast_col].tolist() if ema_fast_col and ema_fast_col in df_slice.columns else []
        ema_slow = df_slice[ema_slow_col].tolist() if ema_slow_col and ema_slow_col in df_slice.columns else []

        all_vals = closes + ema_fast + ema_slow
        all_vals = [v for v in all_vals if v == v]  # filter NaN
        if not all_vals:
            return ["No data"]

        y_min = min(all_vals)
        y_max = max(all_vals)
        y_range = y_max - y_min or 1.0

        chart_h = max(height - 4, 5)
        chart_w = min(width - 12, n_bars)

        grid = [[" "] * chart_w for _ in range(chart_h)]

        def to_row(val: float) -> int:
            return int((y_max - val) / y_range * (chart_h - 1))

        # Plot price as '|' bars
        for i, close in enumerate(closes[-chart_w:]):
            col = i
            row = to_row(close)
            row = max(0, min(chart_h - 1, row))
            grid[row][col] = "│"

        # Overlay EMA_9 as '·'
        for i, val in enumerate(ema_fast[-chart_w:]):
            if val != val:
                continue
            col = i
            row = to_row(val)
            row = max(0, min(chart_h - 1, row))
            if grid[row][col] == " ":
                grid[row][col] = "·"

        # Overlay EMA_21 as '╌'
        for i, val in enumerate(ema_slow[-chart_w:]):
            if val != val:
                continue
            col = i
            row = to_row(val)
            row = max(0, min(chart_h - 1, row))
            if grid[row][col] == " ":
                grid[row][col] = "╌"

        lines = []
        price_labels = [y_max, (y_max + y_min) / 2, y_min]
        label_rows = [0, chart_h // 2, chart_h - 1]

        for r, row in enumerate(grid):
            label = ""
            for lr, pr in zip(label_rows, price_labels):
                if abs(r - lr) <= 0:
                    label = f"{pr:>10.1f} "
                    break
            if not label:
                label = " " * 12
            lines.append(label + "".join(row))

        lines.append(" " * 12 + "─" * chart_w)
        lines.append(" " * 12 + f"│ EMA9=· EMA21=╌ Price=│  ({n_bars} bars)")
        return lines

    def render(self) -> RenderResult:
        df = self.df
        symbol = self.symbol

        if df is None or df.empty:
            return Panel(
                Text("Waiting for data...", style="dim"),
                title=f"[bold cyan]Chart — {symbol}[/]",
                border_style="blue",
            )

        width = self.size.width or 80
        height = self.size.height or 20
        lines = self._build_chart(df, width, height)
        content = Text("\n".join(lines), style="green")

        return Panel(
            content,
            title=f"[bold cyan]Chart — {symbol}[/]",
            border_style="blue",
        )

    def update_data(self, symbol: str, df: pd.DataFrame) -> None:
        self.symbol = symbol
        self.df = df
        self.refresh()
