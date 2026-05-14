import pandas as pd
import pandas_ta as ta

from config import EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD


def compute(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.ta.ema(length=EMA_FAST, append=True)      # col: EMA_9
    df.ta.ema(length=EMA_SLOW, append=True)      # col: EMA_21
    df.ta.vwap(append=True)                      # col: VWAP_D
    df.ta.rsi(length=RSI_PERIOD, append=True)    # col: RSI_14
    df.ta.bbands(length=20, append=True)         # cols: BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
    df.ta.atr(length=ATR_PERIOD, append=True)    # col: ATRr_14
    df.ta.obv(append=True)                       # col: OBV
    df["vol_ratio"] = df["volume"] / df["volume"].rolling(20).mean()
    return df.dropna()


if __name__ == "__main__":
    import numpy as np

    # Build synthetic 200-row OHLCV DataFrame
    np.random.seed(42)
    n = 200
    close = 60000 + np.cumsum(np.random.randn(n) * 100)
    high = close + np.abs(np.random.randn(n) * 50)
    low = close - np.abs(np.random.randn(n) * 50)
    open_ = close + np.random.randn(n) * 30
    volume = np.abs(np.random.randn(n) * 100 + 500)
    timestamps = list(range(n))

    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })

    result = compute(df)
    print(f"Input rows: {len(df)}, Output rows: {len(result)}")
    print(f"Columns: {list(result.columns)}")
    assert f"EMA_{EMA_FAST}" in result.columns, f"Missing EMA_{EMA_FAST}"
    assert f"EMA_{EMA_SLOW}" in result.columns, f"Missing EMA_{EMA_SLOW}"
    assert f"RSI_{RSI_PERIOD}" in result.columns, f"Missing RSI_{RSI_PERIOD}"
    assert "OBV" in result.columns, "Missing OBV"
    assert "vol_ratio" in result.columns, "Missing vol_ratio"
    assert not result.isnull().any().any(), "NaN values found after dropna"
    print("strategy/indicators.py self-test passed")
