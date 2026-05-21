# Crypto Terminal — CLAUDE.md

## What this is
A local, session-based crypto trading terminal built with Python. It streams live OHLCV data from Hyperliquid via CCXT WebSockets, scores signals with technical indicators, routes high-scoring signals through a Groq LLM for a trade decision, and executes paper or live orders via the Hyperliquid SDK. The UI is a Textual TUI.

## How to run
```bash
cd crypto_terminal
pip install -r requirements.txt
cp .env.example .env   # fill in credentials
python main.py
```

## Project layout
```
crypto_terminal/
├── main.py              # entry point
├── config.py            # all tunable constants (symbols, risk, indicators, Groq model)
├── ai/
│   ├── analyst.py       # AsyncGroq client — analyze(signal) → JSON decision
│   └── prompts.py       # system_prompt() + signal_context() builders
├── data/
│   ├── feed.py          # DataFeed — cold_start() + watch_ohlcv WebSocket loop
│   └── state.py         # MarketState — async class-level shared state
├── execution/
│   ├── orders.py        # OrderManager — place_order() + close_position(), CSV logging
│   ├── risk.py          # RiskManager — position_size() + can_trade()
│   └── monitor.py       # PositionMonitor — SL/TP polling loop (5s)
├── strategy/
│   ├── indicators.py    # compute(df) → enriched DataFrame via pandas-ta
│   ├── regime.py        # detect(df) → "trending" | "ranging" | "volatile"
│   └── scorer.py        # score(df, ...) → SignalEvent | None
├── ui/
│   ├── app.py           # TradingTerminal (Textual App) — wires everything together
│   └── panels/
│       ├── chart_panel.py    # ASCII price chart with EMA overlays
│       ├── signal_panel.py   # Latest signal indicators + score
│       ├── ai_panel.py       # Groq decision display
│       ├── position_panel.py # Open positions + unrealised PnL
│       └── log_panel.py      # Scrolling event log
└── logs/trades.csv      # Appended on every open/close
```

## Key config (config.py)
- `PAPER_MODE = True` — set False for live orders (requires real HL credentials)
- `SYMBOLS` — list of Hyperliquid perp symbols to watch
- `PRIMARY_TF = "15m"` — timeframe that drives signal scoring and Groq calls
- `MIN_SIGNAL_SCORE = 60` — signals below this are dropped before reaching Groq
- `GROQ_MODEL` — swap to any Groq-hosted model

## Environment variables (.env)
```
GROQ_API_KEY=gsk_...
HL_WALLET_ADDRESS=0x...
HL_PRIVATE_KEY=0x...
```

## Keyboard bindings (TUI)
| Key | Action |
|-----|--------|
| `q` | Quit (prompts if positions open) |
| `p` | Toggle paper/live mode |
| `s` | Cycle active symbol on chart |
| `h` | Halt / resume signal processing |
| `f` | Flatten all open positions |
| `r` | Reset session PnL counter |

## Signal pipeline (per closed candle on PRIMARY_TF)
1. `indicators.compute(df)` — adds EMA, VWAP, RSI, BB, ATR, OBV, vol_ratio
2. `regime.detect(df)` — classifies market condition
3. `scorer.score(df, ...)` — scores long/short setups 0–100, returns `SignalEvent` if ≥ MIN_SIGNAL_SCORE
4. `risk.can_trade(...)` — checks max positions and daily loss limit
5. `analyst.analyze(signal, ...)` — Groq LLM returns `{decision, conviction, size_pct, stop_loss, take_profit, reason}`
6. If `decision == "execute"` and `conviction >= 65` → `orders.place_order(...)`

## Each module has a self-test
Run any module directly to verify it works in isolation:
```bash
python -m strategy.indicators
python -m strategy.scorer
python -m execution.risk
python -m ai.analyst      # requires GROQ_API_KEY
python -m data.feed       # requires HL credentials (30s timeout test)
```
