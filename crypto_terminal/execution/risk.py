import math

from config import MAX_POSITION_PCT, DAILY_LOSS_LIMIT, MAX_OPEN_POSITIONS


class RiskManager:
    def position_size(
        self,
        account_size: float,
        size_pct: int,
        price: float,
        min_qty: float = 0.0001,
        qty_precision: int = 4,
    ) -> float:
        """Return quantity to trade, rounded down to exchange minimum precision."""
        dollar_amount = account_size * MAX_POSITION_PCT * (size_pct / 100)
        quantity = dollar_amount / price
        # Round down to precision
        factor = 10 ** qty_precision
        quantity = math.floor(quantity * factor) / factor
        return max(quantity, 0.0)

    def can_trade(
        self,
        n_open: int,
        session_pnl: float,
        account_size: float,
    ) -> tuple[bool, str]:
        """Returns (True, '') or (False, reason_string)."""
        if n_open >= MAX_OPEN_POSITIONS:
            return False, f"Max positions ({MAX_OPEN_POSITIONS}) reached"
        if session_pnl <= -(account_size * DAILY_LOSS_LIMIT):
            return False, f"Daily loss limit hit (${session_pnl:.2f})"
        return True, ""


if __name__ == "__main__":
    rm = RiskManager()

    # Sizing test: 10k account, 50% Groq size_pct, price = 67420
    qty = rm.position_size(account_size=10000.0, size_pct=50, price=67420.0)
    expected_dollars = 10000 * 0.05 * 0.50   # $250
    expected_qty = expected_dollars / 67420.0
    print(f"Qty: {qty} (expected ~{expected_qty:.6f})")
    assert qty <= expected_qty, "Quantity exceeds expected maximum"
    assert qty > 0, "Quantity must be positive"

    # can_trade tests
    ok, reason = rm.can_trade(n_open=0, session_pnl=0.0, account_size=10000.0)
    assert ok, "Should be able to trade"

    ok, reason = rm.can_trade(n_open=3, session_pnl=0.0, account_size=10000.0)
    assert not ok and "Max positions" in reason, f"Expected max positions block, got: {reason}"

    ok, reason = rm.can_trade(n_open=0, session_pnl=-250.0, account_size=10000.0)
    assert not ok and "loss limit" in reason, f"Expected loss limit block, got: {reason}"

    ok, reason = rm.can_trade(n_open=0, session_pnl=-199.0, account_size=10000.0)
    assert ok, "Should be allowed at -199 with 2% limit on 10k"

    print("execution/risk.py self-test passed")
