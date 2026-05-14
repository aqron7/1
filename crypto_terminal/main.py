import asyncio
import signal
import sys
from dotenv import load_dotenv

load_dotenv()

from ui.app import TradingTerminal
from data.state import MarketState


def main() -> None:
    app = TradingTerminal()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        async def cleanup():
            positions = await MarketState.get_all_positions()
            if positions:
                print(f"\n{len(positions)} open position(s) detected.")
                answer = input("Flatten all before exit? (y/n): ").strip().lower()
                if answer == "y":
                    from execution.orders import OrderManager
                    om = OrderManager()
                    for symbol in list(positions.keys()):
                        await om.close_position(symbol, "exit_flatten")
                    print("All positions flattened.")
                else:
                    print("Positions left open. Exiting.")
            print("Session ended.")

        asyncio.run(cleanup())


if __name__ == "__main__":
    main()
