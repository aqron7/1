import asyncio
from datetime import datetime
from typing import Optional
import pandas as pd

from config import DAILY_LOSS_LIMIT


class MarketState:
    _lock = asyncio.Lock()
    _candles: dict[str, dict[str, pd.DataFrame]] = {}
    _positions: dict[str, dict] = {}    # symbol -> {side, size, entry, sl, tp}
    _session_pnl: float = 0.0
    _account_size: float = 10000.0      # updated on session start
    _daily_halted: bool = False
    _events: list[str] = []             # rolling event log for log panel

    @classmethod
    async def update_candles(cls, symbol: str, tf: str, df: pd.DataFrame) -> None:
        async with cls._lock:
            if symbol not in cls._candles:
                cls._candles[symbol] = {}
            cls._candles[symbol][tf] = df

    @classmethod
    async def get_candles(cls, symbol: str, tf: str) -> Optional[pd.DataFrame]:
        async with cls._lock:
            return cls._candles.get(symbol, {}).get(tf)

    @classmethod
    async def update_position(cls, symbol: str, position_dict: Optional[dict]) -> None:
        async with cls._lock:
            if position_dict is None:
                cls._positions.pop(symbol, None)
            else:
                cls._positions[symbol] = position_dict

    @classmethod
    async def get_all_positions(cls) -> dict:
        async with cls._lock:
            return dict(cls._positions)

    @classmethod
    async def add_pnl(cls, amount: float) -> None:
        async with cls._lock:
            cls._session_pnl += amount
            if cls._session_pnl <= -(cls._account_size * DAILY_LOSS_LIMIT):
                cls._daily_halted = True

    @classmethod
    async def get_session_pnl(cls) -> float:
        async with cls._lock:
            return cls._session_pnl

    @classmethod
    async def reset_pnl(cls) -> None:
        async with cls._lock:
            cls._session_pnl = 0.0
            cls._daily_halted = False

    @classmethod
    async def set_account_size(cls, size: float) -> None:
        async with cls._lock:
            cls._account_size = size

    @classmethod
    async def get_account_size(cls) -> float:
        async with cls._lock:
            return cls._account_size

    @classmethod
    async def is_halted(cls) -> bool:
        async with cls._lock:
            return cls._daily_halted

    @classmethod
    async def log_event(cls, msg: str) -> None:
        async with cls._lock:
            ts = datetime.now().strftime("%H:%M:%S")
            cls._events.append(f"[{ts}] {msg}")
            if len(cls._events) > 200:
                cls._events = cls._events[-200:]

    @classmethod
    async def get_events(cls) -> list[str]:
        async with cls._lock:
            return list(cls._events)


if __name__ == "__main__":
    import asyncio

    async def test():
        await MarketState.log_event("State module initialized")
        await MarketState.set_account_size(50000.0)
        await MarketState.update_position("BTC/USDC:USDC", {
            "side": "long", "size": 0.01, "entry": 67000.0,
            "sl": 66000.0, "tp": 69000.0
        })
        positions = await MarketState.get_all_positions()
        print(f"Positions: {positions}")

        await MarketState.add_pnl(-100.0)
        pnl = await MarketState.get_session_pnl()
        halted = await MarketState.is_halted()
        print(f"Session PnL: {pnl}, Halted: {halted}")

        events = await MarketState.get_events()
        print(f"Events: {events}")

        print("data/state.py self-test passed")

    asyncio.run(test())
