from config import MAX_OPEN_POSITIONS, MAX_POSITION_PCT, DAILY_LOSS_LIMIT, ATR_SL_MULT, ATR_TP_MULT
from strategy.scorer import SignalEvent


def system_prompt(account_size: float, open_positions: int) -> str:
    return f"""You are a crypto trading risk analyst. You receive structured signal data and return \
a JSON trade decision. You are conservative — skip marginal setups, protect capital.

Account: ${account_size:.2f} | Open positions: {open_positions}/{MAX_OPEN_POSITIONS}
Max size per trade: {MAX_POSITION_PCT*100:.0f}% of account
Session loss limit: {DAILY_LOSS_LIMIT*100:.0f}%

Respond with ONLY a valid JSON object, no other text:
{{
  "decision": "execute" | "skip" | "wait",
  "conviction": 0-100,
  "size_pct": 0-100,
  "stop_loss": float,
  "take_profit": float,
  "reason": "one sentence max"
}}

Rules:
- "execute" only if conviction >= 65
- "wait" if setup is forming but not yet confirmed
- "skip" if risk/reward is poor or regime conflicts with signal side
- size_pct scales with conviction: 65 conviction = 20% size, 100 = 100% size
- stop_loss and take_profit must be actual price levels, not percentages or offsets"""


def signal_context(event: SignalEvent) -> str:
    i = event.indicators
    sl = (event.close - ATR_SL_MULT * event.atr if event.side == "long"
          else event.close + ATR_SL_MULT * event.atr)
    tp = (event.close + ATR_TP_MULT * event.atr if event.side == "long"
          else event.close - ATR_TP_MULT * event.atr)
    return f"""Signal: {event.side.upper()} {event.symbol} on {event.timeframe}
Strategy: {event.strategy_tag} | Regime: {event.regime} | Raw score: {event.score}/100
Price: {event.close} | ATR: {event.atr:.4f}
Suggested SL: {sl:.4f} | Suggested TP: {tp:.4f}

Indicators:
- RSI: {i['rsi']:.1f}
- EMA spread: {i['ema_spread']:.3f}%
- Volume ratio: {i['vol_ratio']:.2f}x 20-bar average
- BB position: {i['bb_pct']:.2f}  (0.0 = lower band, 1.0 = upper band)
- OBV slope: {i['obv_slope']}"""


if __name__ == "__main__":
    sample_event = SignalEvent(
        symbol="BTC/USDC:USDC",
        timeframe="15m",
        side="long",
        score=75,
        close=67420.0,
        atr=320.5,
        regime="trending",
        indicators={
            "rsi": 42.3,
            "ema_spread": 0.45,
            "vol_ratio": 2.3,
            "bb_pct": 0.35,
            "obv_slope": "up",
        },
        strategy_tag="ema_cross",
    )

    sys = system_prompt(account_size=10000.0, open_positions=1)
    usr = signal_context(sample_event)

    print("=== SYSTEM PROMPT ===")
    print(sys)
    print("\n=== USER MESSAGE ===")
    print(usr)
    print("\nai/prompts.py self-test passed")
