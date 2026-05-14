# Symbols must be Hyperliquid perp format
SYMBOLS = ["BTC/USDC:USDC", "ETH/USDC:USDC", "SOL/USDC:USDC"]
TIMEFRAMES = ["1m", "15m", "1h"]
PRIMARY_TF = "15m"
CANDLE_HISTORY = 200

# Risk parameters
MAX_POSITION_PCT   = 0.05    # max 5% of account per trade
DAILY_LOSS_LIMIT   = 0.02    # halt session if down 2%
MAX_OPEN_POSITIONS = 3
MIN_SIGNAL_SCORE   = 60      # 0-100; below this, skip Groq entirely

# Indicator settings
EMA_FAST        = 9
EMA_SLOW        = 21
RSI_PERIOD      = 14
RSI_OVERSOLD    = 35
RSI_OVERBOUGHT  = 65
VOL_SPIKE_MULT  = 2.0        # volume must be 2x 20-bar average
ATR_PERIOD      = 14
ATR_SL_MULT     = 1.5        # stop loss   = entry +/- 1.5 * ATR
ATR_TP_MULT     = 2.5        # take profit = entry +/- 2.5 * ATR

# Groq
GROQ_MODEL       = "llama-3.3-70b-versatile"
GROQ_MAX_TOKENS  = 512
GROQ_TEMPERATURE = 0.1       # low temp = consistent JSON output

# Session
PAPER_MODE  = True           # True = log only, no real orders placed
EXCHANGE_ID = "hyperliquid"


if __name__ == "__main__":
    print("config.py loaded successfully")
    print(f"Symbols: {SYMBOLS}")
    print(f"Timeframes: {TIMEFRAMES}")
    print(f"Primary TF: {PRIMARY_TF}")
    print(f"Paper mode: {PAPER_MODE}")
