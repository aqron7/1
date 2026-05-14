import json
import time
import asyncio

from groq import AsyncGroq

from config import GROQ_MODEL, GROQ_MAX_TOKENS, GROQ_TEMPERATURE
from data.state import MarketState
from strategy.scorer import SignalEvent
from ai.prompts import system_prompt, signal_context


class Analyst:
    def __init__(self):
        self.client = AsyncGroq()   # reads GROQ_API_KEY from env automatically
        self.call_count = 0
        self.total_latency_ms = 0.0

    @property
    def avg_latency_ms(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.total_latency_ms / self.call_count

    async def analyze(
        self,
        signal: SignalEvent,
        account_size: float,
        open_positions: int,
    ) -> dict:
        sys = system_prompt(account_size, open_positions)
        usr = signal_context(signal)
        t0 = time.monotonic()
        try:
            resp = await self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": sys},
                    {"role": "user", "content": usr},
                ],
                max_tokens=GROQ_MAX_TOKENS,
                temperature=GROQ_TEMPERATURE,
                response_format={"type": "json_object"},
            )
            latency_ms = (time.monotonic() - t0) * 1000
            self.call_count += 1
            self.total_latency_ms += latency_ms
            await MarketState.log_event(
                f"[GROQ] call #{self.call_count} latency={latency_ms:.0f}ms "
                f"avg={self.avg_latency_ms:.0f}ms"
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            await MarketState.log_event(f"[GROQ ERROR] {str(e)[:80]}")
            return {
                "decision": "skip",
                "conviction": 0,
                "size_pct": 0,
                "stop_loss": 0.0,
                "take_profit": 0.0,
                "reason": f"AI error: {str(e)[:60]}",
            }


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()

    async def test():
        if not os.getenv("GROQ_API_KEY"):
            print("GROQ_API_KEY not set — skipping live API test")
            print("ai/analyst.py self-test skipped (no API key)")
            return

        analyst = Analyst()
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

        result = await analyst.analyze(sample_event, account_size=10000.0, open_positions=0)
        print(f"Groq response: {json.dumps(result, indent=2)}")

        required_keys = {"decision", "conviction", "size_pct", "stop_loss", "take_profit", "reason"}
        assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"
        assert result["decision"] in ("execute", "skip", "wait"), f"Invalid decision: {result['decision']}"
        print(f"Call count: {analyst.call_count}, Avg latency: {analyst.avg_latency_ms:.0f}ms")
        print("ai/analyst.py self-test passed")

    asyncio.run(test())
