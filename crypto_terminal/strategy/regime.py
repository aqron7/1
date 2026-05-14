import pandas as pd

from config import EMA_FAST, EMA_SLOW


def detect(df: pd.DataFrame) -> str:
    """Detect market regime from enriched DataFrame (output of indicators.compute)."""
    if len(df) < 50:
        return "ranging"

    ema_fast_col = f"EMA_{EMA_FAST}"
    ema_slow_col = f"EMA_{EMA_SLOW}"

    # Find ATR column (pandas-ta names it ATRr_<period>)
    atr_col = next((c for c in df.columns if c.startswith("ATRr_")), None)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    ema_fast = last[ema_fast_col]
    ema_slow = last[ema_slow_col]
    price = last["close"]

    ema_fast_slope = ema_fast - df.iloc[-5][ema_fast_col]
    ema_slow_slope = ema_slow - df.iloc[-5][ema_slow_col]
    ema_spread_pct = abs(ema_fast - ema_slow) / price * 100

    if atr_col and atr_col in df.columns:
        atr_series = df[atr_col].tail(50)
        atr_current = last[atr_col]
        atr_80th = atr_series.quantile(0.80)
        atr_50th = atr_series.quantile(0.50)
    else:
        atr_current = 0
        atr_80th = float("inf")
        atr_50th = float("inf")

    # Volatile: ATR above 80th percentile of its 50-bar range
    if atr_current > atr_80th:
        return "volatile"

    # Trending: EMAs sloping same direction with meaningful spread
    same_direction = (ema_fast_slope > 0 and ema_slow_slope > 0) or \
                     (ema_fast_slope < 0 and ema_slow_slope < 0)
    if same_direction and ema_spread_pct > 0.3:
        return "trending"

    # Ranging: EMAs flat, price inside Bollinger bands, ATR below median
    bb_lower_col = next((c for c in df.columns if c.startswith("BBL_")), None)
    bb_upper_col = next((c for c in df.columns if c.startswith("BBU_")), None)

    inside_bb = True
    if bb_lower_col and bb_upper_col:
        inside_bb = last[bb_lower_col] <= price <= last[bb_upper_col]

    ema_fast_flat = abs(ema_fast_slope) / price * 100 < 0.1
    ema_slow_flat = abs(ema_slow_slope) / price * 100 < 0.1

    if ema_fast_flat and ema_slow_flat and inside_bb and atr_current < atr_50th:
        return "ranging"

    return "ranging"


if __name__ == "__main__":
    import numpy as np
    from strategy.indicators import compute

    np.random.seed(0)
    n = 200

    def make_df(prices):
        high = prices + np.abs(np.random.randn(n) * 50)
        low = prices - np.abs(np.random.randn(n) * 50)
        volume = np.abs(np.random.randn(n) * 100 + 500)
        df = pd.DataFrame({
            "timestamp": list(range(n)),
            "open": prices,
            "high": high,
            "low": low,
            "close": prices,
            "volume": volume,
        })
        return compute(df)

    # Trending: strong uptrend
    trending_prices = 60000 + np.cumsum(np.ones(n) * 200)
    df_trend = make_df(trending_prices)
    r = detect(df_trend)
    print(f"Trending data → regime: {r}")
    assert r == "trending", f"Expected 'trending', got '{r}'"

    # Ranging: flat prices with low volatility
    ranging_prices = 60000 + np.random.randn(n) * 50
    df_range = make_df(ranging_prices)
    r = detect(df_range)
    print(f"Ranging data → regime: {r}")
    assert r in ("ranging", "volatile"), f"Unexpected regime '{r}'"

    # Volatile: random walk with large moves
    volatile_prices = 60000 + np.cumsum(np.random.randn(n) * 800)
    df_vol = make_df(volatile_prices)
    r = detect(df_vol)
    print(f"Volatile data → regime: {r}")

    print("strategy/regime.py self-test passed")
