import asyncio
import os
import time
import pandas as pd
import ccxt.pro as ccxtpro
from typing import Callable, Awaitable

from config import SYMBOLS, TIMEFRAMES, CANDLE_HISTORY
from data.state import MarketState


class DataFeed:
    def __init__(self, on_candle_callback: Callable[[str, str, pd.DataFrame], Awaitable[None]]):
        self.exchange = ccxtpro.hyperliquid({
            "walletAddress": os.getenv("HL_WALLET_ADDRESS", ""),
            "privateKey": os.getenv("HL_PRIVATE_KEY", ""),
        })
        self.candles: dict[str, dict[str, pd.DataFrame]] = {s: {} for s in SYMBOLS}
        self.on_candle = on_candle_callback
        self._last_ts: dict[str, dict[str, int]] = {s: {} for s in SYMBOLS}
        self._running = True

    def _to_dataframe(self, ohlcv: list) -> pd.DataFrame:
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df = df.astype({
            "timestamp": "int64",
            "open": "float64",
            "high": "float64",
            "low": "float64",
            "close": "float64",
            "volume": "float64",
        })
        return df

    async def cold_start(self) -> None:
        await MarketState.log_event("Cold start: fetching historical candles...")
        rest_exchange = ccxtpro.hyperliquid({
            "walletAddress": os.getenv("HL_WALLET_ADDRESS", ""),
            "privateKey": os.getenv("HL_PRIVATE_KEY", ""),
        })
        try:
            for symbol in SYMBOLS:
                for tf in TIMEFRAMES:
                    try:
                        raw = await rest_exchange.fetch_ohlcv(symbol, tf, limit=CANDLE_HISTORY)
                        df = self._to_dataframe(raw)
                        self.candles[symbol][tf] = df
                        await MarketState.update_candles(symbol, tf, df)
                        if tf in self._last_ts[symbol] is False:
                            pass
                        self._last_ts[symbol][tf] = int(df.iloc[-1]["timestamp"]) if not df.empty else 0
                        await MarketState.log_event(
                            f"Cold start: {symbol} {tf} — {len(df)} candles loaded"
                        )
                    except Exception as e:
                        await MarketState.log_event(f"Cold start error {symbol} {tf}: {str(e)[:60]}")
        finally:
            await rest_exchange.close()

    async def _watch_symbol(self, symbol: str, tf: str) -> None:
        retries = 0
        max_retries = 5
        backoff = 2

        while self._running:
            try:
                ohlcv = await self.exchange.watch_ohlcv(symbol, tf)
                if not ohlcv:
                    continue

                df_new = self._to_dataframe(ohlcv)
                latest_ts = int(df_new.iloc[-1]["timestamp"])
                prev_ts = self._last_ts[symbol].get(tf, 0)

                if prev_ts != 0 and latest_ts != prev_ts:
                    # New bar opened — the previous bar is now closed
                    existing = self.candles[symbol].get(tf, pd.DataFrame())
                    if not existing.empty:
                        combined = pd.concat([existing, df_new], ignore_index=True)
                        combined = combined.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
                        combined = combined.tail(CANDLE_HISTORY).reset_index(drop=True)
                    else:
                        combined = df_new
                    self.candles[symbol][tf] = combined
                    await MarketState.update_candles(symbol, tf, combined)
                    await self.on_candle(symbol, tf, combined)
                elif prev_ts == 0:
                    # First update — merge with cold start data
                    existing = self.candles[symbol].get(tf, pd.DataFrame())
                    if not existing.empty:
                        combined = pd.concat([existing, df_new], ignore_index=True)
                        combined = combined.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
                        combined = combined.tail(CANDLE_HISTORY).reset_index(drop=True)
                        self.candles[symbol][tf] = combined
                        await MarketState.update_candles(symbol, tf, combined)

                self._last_ts[symbol][tf] = latest_ts
                retries = 0  # reset on success

            except asyncio.CancelledError:
                break
            except Exception as e:
                retries += 1
                await MarketState.log_event(
                    f"WebSocket error {symbol} {tf} (attempt {retries}): {str(e)[:60]}"
                )
                if retries >= max_retries:
                    await MarketState.log_event(
                        f"Max retries reached for {symbol} {tf}, giving up"
                    )
                    break
                await asyncio.sleep(backoff * (2 ** (retries - 1)))

    async def run(self) -> None:
        await self.cold_start()
        tasks = [self._watch_symbol(s, tf) for s in SYMBOLS for tf in TIMEFRAMES]
        await asyncio.gather(*tasks)

    async def close(self) -> None:
        self._running = False
        await self.exchange.close()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    async def print_candle(symbol: str, tf: str, df: pd.DataFrame) -> None:
        print(f"[CANDLE] {symbol} {tf}: {len(df)} bars, last close={df.iloc[-1]['close']:.2f}")

    async def test():
        feed = DataFeed(on_candle_callback=print_candle)
        print("Starting cold start fetch...")
        try:
            await asyncio.wait_for(feed.run(), timeout=30)
        except asyncio.TimeoutError:
            print("Timeout reached (expected in test)")
        finally:
            await feed.close()

    asyncio.run(test())
