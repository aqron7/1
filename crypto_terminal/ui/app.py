import asyncio
import os
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Static
from textual.reactive import reactive

from config import SYMBOLS, PRIMARY_TF, PAPER_MODE
from data.feed import DataFeed
from data.state import MarketState
from strategy.indicators import compute
from strategy.regime import detect
from strategy.scorer import score, SignalEvent
from ai.analyst import Analyst
from execution.risk import RiskManager
from execution.orders import OrderManager
from execution.monitor import PositionMonitor
from ui.panels.chart_panel import ChartPanel
from ui.panels.signal_panel import SignalPanel
from ui.panels.ai_panel import AIPanel
from ui.panels.position_panel import PositionPanel
from ui.panels.log_panel import LogPanel


class StatusBar(Static):
    DEFAULT_CSS = """
    StatusBar {
        background: $panel;
        color: $text;
        height: 1;
        dock: bottom;
        padding: 0 1;
    }
    """


class TradingTerminal(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    #main-area {
        layout: horizontal;
        height: 1fr;
    }

    #left-col {
        width: 60%;
        layout: vertical;
    }

    #right-col {
        width: 40%;
        layout: vertical;
    }

    ChartPanel {
        height: 60%;
    }

    SignalPanel {
        height: 40%;
    }

    AIPanel {
        height: 34%;
    }

    PositionPanel {
        height: 33%;
    }

    LogPanel {
        height: 33%;
    }
    """

    BINDINGS = [
        Binding("q", "quit_confirm", "Quit"),
        Binding("p", "toggle_paper", "Toggle Paper"),
        Binding("s", "cycle_symbol", "Cycle Symbol"),
        Binding("h", "halt_signals", "Halt Signals"),
        Binding("f", "flatten_all", "Flatten All"),
        Binding("r", "reset_pnl", "Reset PnL"),
    ]

    _active_symbol_idx: int = 0
    _signals_halted: bool = False
    _paper_mode: bool = PAPER_MODE
    _signal_count: int = 0
    _groq_calls: int = 0
    _avg_latency_ms: float = 0.0
    _session_pnl: float = 0.0
    _regime: str = "unknown"
    _latest_price: float = 0.0

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-area"):
            with Vertical(id="left-col"):
                yield ChartPanel(id="chart")
                yield SignalPanel(id="signal")
            with Vertical(id="right-col"):
                yield AIPanel(id="ai")
                yield PositionPanel(id="positions")
                yield LogPanel(id="log")
        yield Footer()
        yield StatusBar(id="statusbar")

    def on_mount(self) -> None:
        self._analyst = Analyst()
        self._risk = RiskManager()
        self._orders = OrderManager()
        self._monitor = PositionMonitor(self._orders)
        self._feed = DataFeed(on_candle_callback=self._on_candle)

        self.run_worker(self._feed.run(), exclusive=False)
        self.run_worker(self._monitor.run(), exclusive=False)
        self.run_worker(self._refresh_loop(), exclusive=False)

    async def _refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(1)
            self._session_pnl = await MarketState.get_session_pnl()
            positions = await MarketState.get_all_positions()
            prices = {}
            for sym in positions:
                df = await MarketState.get_candles(sym, "1m")
                if df is not None and not df.empty:
                    prices[sym] = float(df.iloc[-1]["close"])
            self.query_one("#positions", PositionPanel).update_positions(positions, prices)

            events = await MarketState.get_events()
            self.query_one("#log", LogPanel).update_events(events)

            # Update status bar
            active_symbol = SYMBOLS[self._active_symbol_idx]
            paper_tag = "[PAPER]" if self._paper_mode else "[LIVE]"
            halt_tag = " [HALTED]" if self._signals_halted else ""
            status = (
                f"{paper_tag}{halt_tag}  "
                f"{active_symbol.split('/')[0]} ${self._latest_price:,.2f}  │  "
                f"Session: {self._session_pnl:+.2f}  │  "
                f"Regime: {self._regime}  │  "
                f"Signals: {self._signal_count}  │  "
                f"Groq calls: {self._groq_calls}  │  "
                f"Avg latency: {self._avg_latency_ms:.0f}ms"
            )
            self.query_one("#statusbar", StatusBar).update(status)

    async def _on_candle(self, symbol: str, tf: str, df) -> None:
        if tf != PRIMARY_TF:
            return
        if self._signals_halted:
            return
        if await MarketState.is_halted():
            return

        try:
            enriched = compute(df)
            if enriched.empty:
                return

            regime = detect(enriched)
            self._regime = regime

            active_symbol = SYMBOLS[self._active_symbol_idx]
            if symbol == active_symbol:
                self._latest_price = float(enriched.iloc[-1]["close"])
                self.query_one("#chart", ChartPanel).update_data(symbol, enriched)

            signal: Optional[SignalEvent] = score(enriched, symbol, tf, regime)
            if signal is None:
                return

            self._signal_count += 1
            self.query_one("#signal", SignalPanel).update_signal(signal)

            positions = await MarketState.get_all_positions()
            account_size = await MarketState.get_account_size()

            ok, reason = self._risk.can_trade(
                n_open=len(positions),
                session_pnl=self._session_pnl,
                account_size=account_size,
            )
            if not ok:
                await MarketState.log_event(f"[RISK] Skipping {symbol}: {reason}")
                return

            ai_result = await self._analyst.analyze(signal, account_size, len(positions))
            self._groq_calls = self._analyst.call_count
            self._avg_latency_ms = self._analyst.avg_latency_ms
            signal_info = f"{signal.side.upper()} {symbol} score={signal.score}"
            self.query_one("#ai", AIPanel).update_result(ai_result, signal_info)

            if ai_result.get("decision") == "execute":
                size = self._risk.position_size(
                    account_size=account_size,
                    size_pct=int(ai_result.get("size_pct", 20)),
                    price=signal.close,
                )
                if size > 0:
                    await self._orders.place_order(
                        symbol=signal.symbol,
                        side=signal.side,
                        size=size,
                        stop_loss=float(ai_result.get("stop_loss", signal.close)),
                        take_profit=float(ai_result.get("take_profit", signal.close)),
                        close_price=signal.close,
                        ai_conviction=int(ai_result.get("conviction", 0)),
                        strategy_tag=signal.strategy_tag,
                    )
        except Exception as e:
            await MarketState.log_event(f"[PIPELINE ERROR] {str(e)[:80]}")

    async def action_quit_confirm(self) -> None:
        positions = await MarketState.get_all_positions()
        if positions:
            await MarketState.log_event(f"Quit requested — {len(positions)} open positions")
            self.notify(
                f"You have {len(positions)} open position(s). Press 'f' to flatten first, or 'q' again to force quit.",
                title="Open Positions",
                severity="warning",
            )
            # Second press quits; register a one-shot flag
            if not getattr(self, "_quit_pending", False):
                self._quit_pending = True
                return
        await self._shutdown()

    async def _shutdown(self) -> None:
        self._monitor.stop()
        await self._feed.close()
        self.exit()

    async def action_toggle_paper(self) -> None:
        if self._paper_mode:
            self.notify(
                "Type CONFIRM to switch to LIVE trading mode.",
                title="Switch to Live Mode",
                severity="warning",
            )
            # Simplified: just notify; full confirmation requires an input modal
            await MarketState.log_event("[WARNING] Live mode toggle requested — implement PIN confirm")
        else:
            self._paper_mode = True
            self._orders.paper = True
            await MarketState.log_event("Switched to PAPER mode")

    async def action_cycle_symbol(self) -> None:
        self._active_symbol_idx = (self._active_symbol_idx + 1) % len(SYMBOLS)
        new_symbol = SYMBOLS[self._active_symbol_idx]
        df = await MarketState.get_candles(new_symbol, PRIMARY_TF)
        if df is not None and not df.empty:
            try:
                enriched = compute(df)
                self.query_one("#chart", ChartPanel).update_data(new_symbol, enriched)
            except Exception:
                self.query_one("#chart", ChartPanel).update_data(new_symbol, df)
        await MarketState.log_event(f"Active symbol → {new_symbol}")

    async def action_halt_signals(self) -> None:
        self._signals_halted = not self._signals_halted
        state = "HALTED" if self._signals_halted else "RESUMED"
        await MarketState.log_event(f"Signal processing {state}")
        self.notify(f"Signals {state}", severity="warning" if self._signals_halted else "information")

    async def action_flatten_all(self) -> None:
        positions = await MarketState.get_all_positions()
        if not positions:
            self.notify("No open positions to flatten")
            return
        for symbol in list(positions.keys()):
            await self._orders.close_position(symbol, "manual_flatten")
        await MarketState.log_event(f"Flattened {len(positions)} position(s)")
        self.notify(f"Flattened {len(positions)} position(s)")
        self._quit_pending = False

    async def action_reset_pnl(self) -> None:
        await MarketState.reset_pnl()
        self._session_pnl = 0.0
        await MarketState.log_event("Session PnL counter reset")
        self.notify("Session PnL reset to $0.00")
