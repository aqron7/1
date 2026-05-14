import asyncio

from data.state import MarketState
from execution.orders import OrderManager


class PositionMonitor:
    def __init__(self, order_manager: OrderManager):
        self.orders = order_manager
        self._running = True

    async def _latest_price(self, symbol: str) -> float:
        df = await MarketState.get_candles(symbol, "1m")
        if df is not None and not df.empty:
            return float(df.iloc[-1]["close"])
        return 0.0

    def _sl_hit(self, pos: dict, price: float) -> bool:
        if pos["side"] == "long":
            return price <= pos["sl"]
        else:
            return price >= pos["sl"]

    def _tp_hit(self, pos: dict, price: float) -> bool:
        if pos["side"] == "long":
            return price >= pos["tp"]
        else:
            return price <= pos["tp"]

    def _calc_pnl(self, pos: dict, exit_price: float) -> float:
        entry = pos["entry"]
        size = pos["size"]
        if pos["side"] == "long":
            return (exit_price - entry) * size
        else:
            return (entry - exit_price) * size

    async def run(self) -> None:
        while self._running:
            try:
                positions = await MarketState.get_all_positions()
                for symbol, pos in positions.items():
                    price = await self._latest_price(symbol)
                    if price == 0.0:
                        continue
                    if self._sl_hit(pos, price):
                        pnl = self._calc_pnl(pos, price)
                        await self.orders.close_position(symbol, "stop_loss")
                        await MarketState.log_event(f"SL hit {symbol}: {pnl:+.2f}")
                    elif self._tp_hit(pos, price):
                        pnl = self._calc_pnl(pos, price)
                        await self.orders.close_position(symbol, "take_profit")
                        await MarketState.log_event(f"TP hit {symbol}: {pnl:+.2f}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                await MarketState.log_event(f"[MONITOR ERROR] {str(e)[:80]}")
            await asyncio.sleep(5)

    def stop(self) -> None:
        self._running = False


if __name__ == "__main__":
    import asyncio
    import pandas as pd

    async def test():
        om = OrderManager()

        # Inject a fake position into MarketState
        await MarketState.update_position("BTC/USDC:USDC", {
            "side": "long",
            "size": 0.001,
            "entry": 67000.0,
            "sl": 66000.0,
            "tp": 69000.0,
            "ai_conviction": 70,
            "strategy_tag": "ema_cross",
            "open_ts": "2024-01-01T00:00:00",
        })

        # Inject a candle that hits the TP
        df = pd.DataFrame([{
            "timestamp": 1,
            "open": 69000.0,
            "high": 69200.0,
            "low": 68800.0,
            "close": 69100.0,
            "volume": 100.0,
        }])
        await MarketState.update_candles("BTC/USDC:USDC", "1m", df)

        monitor = PositionMonitor(om)
        # Run one iteration manually
        positions = await MarketState.get_all_positions()
        print(f"Positions before: {list(positions.keys())}")

        for symbol, pos in positions.items():
            price = await monitor._latest_price(symbol)
            print(f"Price: {price}, TP: {pos['tp']}, TP hit: {monitor._tp_hit(pos, price)}")
            if monitor._tp_hit(pos, price):
                pnl = monitor._calc_pnl(pos, price)
                await om.close_position(symbol, "take_profit")
                await MarketState.log_event(f"TP hit {symbol}: {pnl:+.2f}")

        positions_after = await MarketState.get_all_positions()
        print(f"Positions after: {list(positions_after.keys())}")
        assert "BTC/USDC:USDC" not in positions_after, "Position should be closed"

        events = await MarketState.get_events()
        print(f"Events: {events[-3:]}")
        print("execution/monitor.py self-test passed")

    asyncio.run(test())
