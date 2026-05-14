import os
import asyncio
from datetime import datetime, timezone

import aiofiles

from config import PAPER_MODE
from data.state import MarketState


TRADES_CSV = os.path.join(os.path.dirname(__file__), "..", "logs", "trades.csv")
CSV_HEADER = "timestamp,symbol,side,size,entry,exit,pnl,sl,tp,ai_conviction,strategy_tag\n"


async def _ensure_csv() -> None:
    os.makedirs(os.path.dirname(os.path.abspath(TRADES_CSV)), exist_ok=True)
    if not os.path.exists(TRADES_CSV):
        async with aiofiles.open(TRADES_CSV, "w") as f:
            await f.write(CSV_HEADER)


async def _append_csv(row: dict) -> None:
    await _ensure_csv()
    line = (
        f"{row['timestamp']},{row['symbol']},{row['side']},{row['size']},"
        f"{row['entry']},{row.get('exit', '')},"
        f"{row.get('pnl', '')},"
        f"{row['sl']},{row['tp']},"
        f"{row.get('ai_conviction', '')},"
        f"{row.get('strategy_tag', '')}\n"
    )
    async with aiofiles.open(TRADES_CSV, "a") as f:
        await f.write(line)


class OrderManager:
    def __init__(self):
        self.paper = PAPER_MODE
        self._exchange = None
        if not self.paper:
            self._init_live_exchange()

    def _init_live_exchange(self) -> None:
        try:
            from hyperliquid.exchange import Exchange
            from hyperliquid.utils import constants
            private_key = os.getenv("HL_PRIVATE_KEY", "")
            wallet_address = os.getenv("HL_WALLET_ADDRESS", "")
            self._exchange = Exchange(private_key, constants.MAINNET_API_URL, wallet_addr=wallet_address)
        except Exception as e:
            raise RuntimeError(f"Failed to init Hyperliquid SDK: {e}") from e

    async def place_order(
        self,
        symbol: str,
        side: str,
        size: float,
        stop_loss: float,
        take_profit: float,
        close_price: float = 0.0,
        ai_conviction: int = 0,
        strategy_tag: str = "",
    ) -> dict:
        ts = datetime.now(timezone.utc).isoformat()

        if self.paper:
            entry = close_price
            fill = {
                "timestamp": ts,
                "symbol": symbol,
                "side": side,
                "size": size,
                "entry": entry,
                "sl": stop_loss,
                "tp": take_profit,
                "ai_conviction": ai_conviction,
                "strategy_tag": strategy_tag,
            }
            await MarketState.update_position(symbol, {
                "side": side,
                "size": size,
                "entry": entry,
                "sl": stop_loss,
                "tp": take_profit,
                "ai_conviction": ai_conviction,
                "strategy_tag": strategy_tag,
                "open_ts": ts,
            })
            await _append_csv(fill)
            await MarketState.log_event(
                f"[PAPER] {side.upper()} {symbol} size={size} entry={entry:.2f} "
                f"sl={stop_loss:.2f} tp={take_profit:.2f}"
            )
            return fill
        else:
            return await self._place_live_order(
                symbol, side, size, stop_loss, take_profit,
                close_price, ai_conviction, strategy_tag, ts
            )

    async def _place_live_order(
        self, symbol, side, size, stop_loss, take_profit,
        close_price, ai_conviction, strategy_tag, ts
    ) -> dict:
        try:
            is_buy = side == "long"
            # Convert symbol to Hyperliquid coin format (e.g., "BTC/USDC:USDC" -> "BTC")
            coin = symbol.split("/")[0]
            result = self._exchange.market_open(coin, is_buy, size)
            if result["status"] != "ok":
                raise RuntimeError(f"Order failed: {result}")

            entry = close_price  # approximate; real fill price from result if available
            fill = {
                "timestamp": ts,
                "symbol": symbol,
                "side": side,
                "size": size,
                "entry": entry,
                "sl": stop_loss,
                "tp": take_profit,
                "ai_conviction": ai_conviction,
                "strategy_tag": strategy_tag,
            }
            await MarketState.update_position(symbol, {
                "side": side, "size": size, "entry": entry,
                "sl": stop_loss, "tp": take_profit,
                "ai_conviction": ai_conviction, "strategy_tag": strategy_tag,
                "open_ts": ts,
            })
            await _append_csv(fill)
            await MarketState.log_event(
                f"[LIVE] {side.upper()} {symbol} size={size} entry={entry:.2f}"
            )
            return fill
        except Exception as e:
            await MarketState.log_event(f"[ORDER ERROR] {str(e)[:80]}")
            return {"error": str(e)}

    async def close_position(self, symbol: str, reason: str) -> None:
        pos = (await MarketState.get_all_positions()).get(symbol)
        if not pos:
            return

        ts = datetime.now(timezone.utc).isoformat()
        entry = pos["entry"]
        side = pos["side"]
        size = pos["size"]

        # Get latest price as exit price
        df = await MarketState.get_candles(symbol, "1m")
        exit_price = float(df.iloc[-1]["close"]) if df is not None and not df.empty else entry

        pnl = (exit_price - entry) * size if side == "long" else (entry - exit_price) * size

        if not self.paper:
            try:
                coin = symbol.split("/")[0]
                is_buy = side == "short"  # reverse to close
                self._exchange.market_open(coin, is_buy, size)
            except Exception as e:
                await MarketState.log_event(f"[CLOSE ERROR] {str(e)[:80]}")

        row = {
            "timestamp": ts,
            "symbol": symbol,
            "side": side,
            "size": size,
            "entry": entry,
            "exit": exit_price,
            "pnl": round(pnl, 4),
            "sl": pos["sl"],
            "tp": pos["tp"],
            "ai_conviction": pos.get("ai_conviction", ""),
            "strategy_tag": pos.get("strategy_tag", ""),
        }
        await _append_csv(row)
        await MarketState.update_position(symbol, None)
        await MarketState.add_pnl(pnl)
        await MarketState.log_event(
            f"[CLOSE] {symbol} reason={reason} pnl={pnl:+.2f}"
        )


if __name__ == "__main__":
    import asyncio

    async def test():
        om = OrderManager()
        assert om.paper is True, "Must be in paper mode for tests"

        fill = await om.place_order(
            symbol="BTC/USDC:USDC",
            side="long",
            size=0.001,
            stop_loss=66000.0,
            take_profit=69000.0,
            close_price=67420.0,
            ai_conviction=75,
            strategy_tag="ema_cross",
        )
        print(f"Paper fill: {fill}")
        assert fill["symbol"] == "BTC/USDC:USDC"
        assert fill["side"] == "long"

        positions = await MarketState.get_all_positions()
        assert "BTC/USDC:USDC" in positions, "Position not stored in MarketState"

        # Verify CSV written
        import os
        assert os.path.exists(TRADES_CSV), "trades.csv not created"
        async with aiofiles.open(TRADES_CSV, "r") as f:
            contents = await f.read()
        print(f"CSV contents:\n{contents}")
        assert "BTC/USDC:USDC" in contents, "Trade not in CSV"

        await om.close_position("BTC/USDC:USDC", "test_close")
        positions = await MarketState.get_all_positions()
        assert "BTC/USDC:USDC" not in positions, "Position should be removed after close"

        print("execution/orders.py self-test passed")

    asyncio.run(test())
