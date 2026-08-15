#!/usr/bin/env python3
"""
Swing-trading bot: Implements a proven swing trading strategy using
technical indicators for trend, RSI for momentum, MACD for entry/exec
sys.path.append(os.path.dirname(os.path.dirname(os.path to EMA, RSI, and MACD indicators.
Runs in paper trading mode (no real orders placed).

Strategy:
1. Trend Filter: Price > EMA20 for uptrend, Price < EMA20 for downtrend
2. Momentum Filter: RSI between 30-70 (avoid extremes)
3. Entry Signal: MACD line crosses above signal line (buy) or below (sell)
4. Volume Confirmation: Current volume > 20-period average volume
5. Risk Management: Fixed 2% stop loss, 4% take profit (1:2 risk-reward)

Run:
    python -m strategy.swing_bot
or
    python strategy/swing_bot.py
"""

import sys
import os
import time
import signal
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Yahoo Finance API instead of Angel One
from broker.yahoo_finance import YahooFinanceAPI, get_historical_data_for_indicators

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
# Watch‑list refresh settings (seconds)
_WATCHLIST_REFRESH_INTERVAL = 4 * 60 * 60   # 4 hours
_last_watchlist_refresh = 0
WATCH_LIST_INFO: list[dict] = []          # will be filled at startup; each dict: {symbol, exchange, symboltoken}

# Strategy Parameters
EMA_FAST = 12
EMA_SLOW = 26
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
VOLUME_MA_PERIOD = 20

# Risk Management
STOP_LOSS_PCT = 0.02  # 2% stop loss
TAKE_PROFIT_PCT = 0.04  # 4% take profit (1:2 risk-reward)

# Data Parameters
CHART_INTERVAL = "FIVE_MINUTE"  # Use 5-minute candles for analysis
LOOKBACK_PERIODS = 50  # Number of candles to fetch for calculations (dynamic based on indicators)

POLL_INTERVAL_SEC = 3600  # How often to check for new signals
LOG_FILE = None  # Set to a path if you want file logging

# ----------------------------------------------------------------------
# Global state
# ----------------------------------------------------------------------
_shutdown_requested = False

# Paper trading state
positions: Dict[str, Dict] = {}  # symbol -> position info
# Position info: {
#   'entry_price': float,
#   'quantity': int,
#   'stop_loss': float,
#   'take_profit': float,
#   'entry_time': datetime,
#   'side': str  # 'LONG' or 'SHORT'
# }

# ----------------------------------------------------------------------
# Signal handling
# ----------------------------------------------------------------------
def _signal_handler(sig, frame):
    global _shutdown_requested
    print("\n[INFO] Shutdown signal received – finishing current cycle…")
    _shutdown_requested = True

signal.signal(signal.SIGINT, _signal_handler)   # Ctrl‑C
signal.signal(signal.SIGTERM, _signal_handler)  # termination

# ----------------------------------------------------------------------
# Logging helper
# ----------------------------------------------------------------------
def log_print(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    if LOG_FILE:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")

# Telegram Notification Settings
# To enable: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as environment variables
# Get BOT_TOKEN from @BotFather on Telegram
# Get CHAT_ID from @userinfobot or by sending a message to your bot and checking
# https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Get from @BotFather
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Your chat ID
TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
if TELEGRAM_ENABLED:
    log_print("[INFO] Telegram notifications enabled")
else:
    log_print("[INFO] Telegram notifications disabled (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable)")

# ----------------------------------------------------------------------
# Telegram Notification Helper
# ----------------------------------------------------------------------
def escape_telegram_text(text: str) -> str:
    """Escape Telegram Markdown special characters in text for safe insertion."""
    if not isinstance(text, str):
        text = str(text)
    # Escape _ and * to prevent them from being interpreted as Markdown formatting
    return text.replace('_', r'\_').replace('*', r'\*')


def send_telegram_message(message: str):
    """Send a message via Telegram bot"""
    if not TELEGRAM_ENABLED:
        log_print("[INFO] Telegram notifications disabled (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)")
        return

    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            log_print(f"[WARN] Telegram message failed: {response.text}")
        else:
            log_print("[INFO] Telegram message sent successfully")
    except Exception as e:
        log_print(f"[WARN] Failed to send Telegram message: {e}")

# ----------------------------------------------------------------------
# Technical Indicators
# ----------------------------------------------------------------------
def calculate_ema(prices: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average"""
    if len(prices) < period:
        return []

    multiplier = 2 / (period + 1)
    ema = []

    # Start with SMA for first EMA value
    sma = sum(prices[:period]) / period
    ema.append(sma)

    # Calculate EMA for remaining values
    for price in prices[period:]:
        ema_value = (price * multiplier) + (ema[-1] * (1 - multiplier))
        ema.append(ema_value)

    # Pad beginning with None values to match original length
    return [None] * (len(prices) - len(ema)) + ema

def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """Calculate Relative Strength Index"""
    if len(prices) < period + 1:
        return []

    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [delta if delta > 0 else 0 for delta in deltas]
    losses = [-delta if delta < 0 else 0 for delta in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    rsi = [100 - (100 / (1 + rs))]

    # Calculate remaining RSI values
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else 0
        rsi.append(100 - (100 / (1 + rs)))

    # Pad beginning with None values
    return [None] * (len(prices) - len(rsi)) + rsi

def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[float], List[float], List[float]]:
    """Calculate MACD (Moving Average Convergence Divergence)
    Returns: (macd_line, signal_line, histogram)
    """
    if len(prices) < max(fast, slow):
        return [], [], []

    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)

    # Calculate MACD line
    macd_line = []
    for f, s in zip(ema_fast, ema_slow):
        if f is not None and s is not None:
            macd_line.append(f - s)
        else:
            macd_line.append(None)

    # Calculate signal line (EMA of MACD line)
    # Filter out None values for signal calculation
    valid_macd = [x for x in macd_line if x is not None]
    if len(valid_macd) >= signal:
        signal_line_raw = calculate_ema(valid_macd, signal)
        # Pad the beginning to align with original series
        padding_needed = len(macd_line) - len(signal_line_raw)
        signal_line = [None] * padding_needed + signal_line_raw
    else:
        signal_line = [None] * len(macd_line)

    # Calculate histogram
    histogram = []
    for macd, signal_val in zip(macd_line, signal_line):
        if macd is not None and signal_val is not None:
            histogram.append(macd - signal_val)
        else:
            histogram.append(None)

    return macd_line, signal_line, histogram

# ----------------------------------------------------------------------
# Data fetching and processing
# ----------------------------------------------------------------------
def get_historical_data(api: YahooFinanceAPI, symbol: str) -> Optional[List[dict]]:
    """Fetch historical candle data for indicator calculation using Yahoo Finance"""
    try:
        # Use our Yahoo Finance specific helper function
        candles = get_historical_data_for_indicators(
            symbol=symbol,
            interval=CHART_INTERVAL,
            lookback_periods=LOOKBACK_PERIODS
        )
        return candles
    except Exception as e:
        log_print(f"[WARN] {symbol}: Failed to get historical data: {e}")
        return None

# ----------------------------------------------------------------------
# Paper Trading Functions
# ----------------------------------------------------------------------
def calculate_position_size(price: float, risk_percent: float = 0.02) -> int:
    """Calculate position size based on risk percentage
    For simplicity, we'll use a fixed amount per trade
    In a real system, this would be based on account size and risk tolerance
    """
    # For paper trading, let's use a fixed notional value of ~₹50,000 per trade
    # This can be adjusted based on stock price
    target_notional = 50000
    quantity = max(1, int(target_notional / price))
    return quantity

def open_position(symbol: str, side: str, entry_price: float, api: YahooFinanceAPI):
    """Open a new paper trading position"""
    global positions

    if symbol in positions:
        log_print(f"[INFO] {symbol}: Already have position, skipping")
        return

    quantity = calculate_position_size(entry_price)

    if side == "BUY":
        stop_loss = entry_price * (1 - STOP_LOSS_PCT)
        take_profit = entry_price * (1 + TAKE_PROFIT_PCT)
        position_side = "LONG"
    else:  # SELL
        stop_loss = entry_price * (1 + STOP_LOSS_PCT)
        take_profit = entry_price * (1 - TAKE_PROFIT_PCT)
        position_side = "SHORT"

    positions[symbol] = {
        'entry_price': entry_price,
        'quantity': quantity,
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'entry_time': datetime.now(),
        'side': position_side
    }

    log_print(f"[TRADE] {symbol}: OPENED {position_side} {quantity} shares @ ₹{entry_price:.2f}")
    log_print(f"         SL: ₹{stop_loss:.2f} | TP: ₹{take_profit:.2f}")

    # Send trade opened message to Telegram
    if TELEGRAM_ENABLED:
        emoji = "📈" if side == "BUY" else "📉"
        trade_msg = f"{emoji} *Position Opened*\n\n"
        trade_msg += f"Symbol: {escape_telegram_text(symbol)}\n"
        trade_msg += f"Action: {'BUY (LONG)' if side == 'BUY' else 'SELL (SHORT)'}\n"
        trade_msg += f"Quantity: {quantity}\n"
        trade_msg += f"Entry Price: ₹{entry_price:.2f}\n"
        trade_msg += f"Stop Loss: ₹{stop_loss:.2f}\n"
        trade_msg += f"Take Profit: ₹{take_profit:.2f}\n"
        trade_msg += f"Time: {escape_telegram_text(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
        send_telegram_message(trade_msg)

def check_position_exits(symbol: str, current_price: float):
    """Check if existing position should be closed"""
    global positions

    if symbol not in positions:
        return

    pos = positions[symbol]
    exit_price = None
    exit_reason = None

    if pos['side'] == 'LONG':
        if current_price <= pos['stop_loss']:
            exit_price = pos['stop_loss']
            exit_reason = "STOP_LOSS"
        elif current_price >= pos['take_profit']:
            exit_price = pos['take_profit']
            exit_reason = "TAKE_PROFIT"
    else:  # SHORT
        if current_price >= pos['stop_loss']:
            exit_price = pos['stop_loss']
            exit_reason = "STOP_LOSS"
        elif current_price <= pos['take_profit']:
            exit_price = pos['take_profit']
            exit_reason = "TAKE_PROFIT"

    if exit_price is not None:
        # Calculate P&L
        if pos['side'] == 'LONG':
            pnl = (exit_price - pos['entry_price']) * pos['quantity']
            pnl_pct = ((exit_price / pos['entry_price']) - 1) * 100
        else:  # SHORT
            pnl = (pos['entry_price'] - exit_price) * pos['quantity']
            pnl_pct = ((pos['entry_price'] / exit_price) - 1) * 100

        log_print(f"[TRADE] {symbol}: CLOSED {pos['side']} @ ₹{exit_price:.2f} ({exit_reason})")
        log_print(f"         P&L: ₹{pnl:.2f} ({pnl_pct:+.2f}%)")

        # Remove position
        del positions[symbol]

        # Send trade closed message to Telegram
        if TELEGRAM_ENABLED:
            pnl_emoji = "💰" if pnl >= 0 else "💸"
            exit_emoji = "🛑" if exit_reason == "STOP_LOSS" else "🎯"
            close_msg = f"{pnl_emoji} *Position Closed*\n\n"
            close_msg += f"Symbol: {escape_telegram_text(symbol)}\n"
            close_msg += f"Side: {pos['side']}\n"
            close_msg += f"Exit Reason: {exit_reason}\n"
            close_msg += f"Quantity: {pos['quantity']}\n"
            close_msg += f"Entry Price: ₹{pos['entry_price']:.2f}\n"
            close_msg += f"Exit Price: ₹{exit_price:.2f}\n"
            close_msg += f"P&L: ₹{pnl:.2f} ({pnl_pct:+.2f}%)\n"
            close_msg += f"Time: {escape_telegram_text(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
            send_telegram_message(close_msg)

def update_positions(current_prices: Dict[str, float]):
    """Update all open positions with current prices"""
    for symbol, price in current_prices.items():
        if symbol in positions:
            check_position_exits(symbol, price)

# ----------------------------------------------------------------------
# Main trading loop
# ----------------------------------------------------------------------
def main(csv_file="ind_nifty50list.csv"):

    api = YahooFinanceAPI()

    try:
        log_print("Logging in to Yahoo Finance …")
        api.login()
        log_print("Login successful.")
    except Exception as e:
        log_print(f"[ERROR] Login failed: {e}")
        sys.exit(1)

    # Build initial watch‑list (top NSE performers from specified CSV)
    try:
        top_stocks = api.get_top_nse_performers(limit=50, criteria="percent_change", csv_file=csv_file)
        # Each stock dict already contains exchange and symboltoken from the API
        global WATCH_LIST_INFO
        """
        "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "APOLLOTYRE", "ASIANPAINT",
            "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BAJAJHLDNG",
            "BEL", "BHARTIARTL", "BIOCON", "BPCL", "BRITANNIA", "CIPLA",
            "COALINDIA", "DIVISLAB", "DRREDDY", "EICHERMOT", "GAIL", "GRASIM",
            "HCLTECH", "HDFC", "HDFCBANK", "HEROMOTOCO", "HINDALCO", "HAL",
            "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY", "IOC", "ITC",
            "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NESTLEIND",
            "NTPC", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHREECEM",
            "SHRIRAMFIN", "SUNPHARMA", "TATACONSUM", "TATAMOTORS", "TATASTEEL",
            "TCS", "TECHM", "TITAN", "ULTRACEMCO", "UPL", "WIPRO"
            """
        WATCH_LIST_INFO = [
            {
                "symbol": s["symbol"],
                "exchange": s.get("exchange", "NSE"),
                "symboltoken": s.get("symboltoken", "")
            }
            for s in top_stocks if s.get("symbol")
        ]
        _last_watchlist_refresh = time.time()
        log_print(f"[INFO] Watch list built with {len(WATCH_LIST_INFO)} symbols "
                  f"(top by % change): {[s['symbol'] for s in WATCH_LIST_INFO[:5]]}…")
    except Exception as e:
        log_print(f"[WARN] Could not fetch dynamic watch list: {e}")
        log_print("[INFO] Falling back to static list.")
        static_symbols = [
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
            "SBIN", "BHARTIARTL", "KOTAKBANK", "LT"
        ]
        WATCH_LIST_INFO = []
        for sym in static_symbols:
            try:
                info = api.symbol_lookup(sym)
                WATCH_LIST_INFO.append({
                    "symbol": sym,
                    "exchange": info["exchange"],
                    "symboltoken": info["symboltoken"]
                })
            except Exception as lookup_err:
                log_print(f"[WARN] Symbol lookup failed for {sym}: {lookup_err}")
                # Skip this symbol; it shouldn't happen for the static list
        _last_watchlist_refresh = time.time()

    log_print(f"Starting swing trading bot for {len(WATCH_LIST_INFO)} symbols")
    log_print(f"Using {CHART_INTERVAL} charts with {LOOKBACK_PERIODS} lookback periods")
    log_print(f"Polling every {POLL_INTERVAL_SEC} seconds")
    log_print("Press Ctrl‑C to stop.\n")

    # Send startup message to Telegram
    if TELEGRAM_ENABLED:
        startup_message = f"🚀 *Swing Bot Started*\n\n"
        startup_message += f"• Monitoring {len(WATCH_LIST_INFO)} symbols\n"
        startup_message += f"• Timeframe: {escape_telegram_text(CHART_INTERVAL)}\n"
        startup_message += f"• Poll interval: {POLL_INTERVAL_SEC}s\n"
        startup_message += f"• Strategy: EMA20 + RSI(14) + MACD(12,26,9) + Volume\n"
        startup_message += f"• Risk: {STOP_LOSS_PCT*100}% SL / {TAKE_PROFIT_PCT*100}% TP\n"
        send_telegram_message(startup_message)

    # Track last prices for change calculation (keyed by symbol)
    last_prices = {item["symbol"]: None for item in WATCH_LIST_INFO}

    try:
        # while not _shutdown_requested:
        # Refresh watch list periodically
        now = time.time()
        if now - _last_watchlist_refresh > _WATCHLIST_REFRESH_INTERVAL:
            try:
                fresh = api.get_top_nse_performers(limit=50, criteria="percent_change", csv_file=csv_file)
                new_info = [
                    {
                        "symbol": s["symbol"],
                        "exchange": s.get("exchange", "NSE"),
                        "symboltoken": s.get("symboltoken", "")
                    }
                    for s in fresh if s.get("symbol")
                ]
                if new_info:
                    WATCH_LIST_INFO[:] = new_info
                    _last_watchlist_refresh = now
                    log_print(f"[INFO] Watch list refreshed ({len(WATCH_LIST_INFO)} symbols)")
                # Preserve known prices where possible
                preserved = {item["symbol"]: last_prices.get(item["symbol"]) for item in WATCH_LIST_INFO}
                last_prices = {item["symbol"]: preserved.get(item["symbol"]) for item in WATCH_LIST_INFO}
            except Exception as e:
                log_print(f"[WARN] Watch list refresh failed: {e}")

        loop_start = time.time()
        current_prices = {}
        iteration_results = []

        # Send start scanning message to Telegram
        if TELEGRAM_ENABLED:
            start_time = datetime.fromtimestamp(loop_start).strftime('%Y-%m-%d %H:%M:%S')
            telegram_message = f"🔍 *Swing Bot Scan Started*\n\n"
            telegram_message += f"• Time: {escape_telegram_text(start_time)}\n"
            telegram_message += f"• Monitoring: {len(WATCH_LIST_INFO)} symbols\n"
            telegram_message += f"• Timeframe: {escape_telegram_text(CHART_INTERVAL)}\n"
            send_telegram_message(telegram_message)

        # Process each symbol
        for item in WATCH_LIST_INFO:
            sym = item["symbol"]
            exch = item["exchange"]
            tok = item["symboltoken"]
            try:
                # Get current LTP
                ltp = api.get_ltp(exchange=exch, tradingsymbol=f"{sym}-EQ", symboltoken=tok)
                current_prices[sym] = ltp

                # Calculate price change
                prev = last_prices[sym]
                if prev is None:
                    delta = 0.0
                    delta_pct = 0.0
                    delta_str = "–"
                else:
                    delta = ltp - prev
                    delta_pct = (delta / prev) * 100 if prev != 0 else 0.0
                    delta_str = f"{delta:+.2f} ({delta_pct:+.2f}%)"

                # Update last price
                last_prices[sym] = ltp

                # Get historical data and calculate indicators
                candles = get_historical_data(api, sym)
                if candles is None:
                    log_print(f"[WARN] {sym}-EQ: Could not fetch historical data")
                    log_print(f"{sym}-EQ: ₹{ltp:,.2f}  Δ {delta_str}")
                    continue

                # Calculate indicators from candle data (moved inside loop for clarity)
                if not candles or len(candles) < max(EMA_SLOW, RSI_PERIOD, MACD_SLOW, VOLUME_MA_PERIOD):
                    log_print(f"[DEBUG] Not enough candles for indicators: {len(candles) if candles else 0} < {max(EMA_SLOW, RSI_PERIOD, MACD_SLOW, VOLUME_MA_PERIOD)}")
                    log_print(f"{sym}-EQ: ₹{ltp:,.2f}  Δ {delta_str}")
                    continue

                closes = [c['close'] for c in candles]
                volumes = [c['volume'] for c in candles]

                # Calculate indicators
                ema_fast = calculate_ema(closes, EMA_FAST)
                ema_slow = calculate_ema(closes, EMA_SLOW)
                rsi = calculate_rsi(closes, RSI_PERIOD)
                macd_line, signal_line, histogram = calculate_macd(closes, MACD_FAST, MACD_SLOW, MACD_SIGNAL)

                # Volume moving average
                volume_ma = []
                if len(volumes) >= VOLUME_MA_PERIOD:
                    for i in range(len(volumes)):
                        if i < VOLUME_MA_PERIOD - 1:
                            volume_ma.append(None)
                        else:
                            vol_sum = sum(volumes[i-VOLUME_MA_PERIOD+1:i+1])
                            volume_ma.append(vol_sum / VOLUME_MA_PERIOD)
                else:
                    volume_ma = [None] * len(volumes)

                # Debug: show latest values
                if closes:
                    log_print(f"[DEBUG] Latest close: {closes[-1]:.2f}")
                if ema_slow:
                    # Find latest non-none EMA
                    latest_ema_slow = next((x for x in reversed(ema_slow) if x is not None), None)
                    if latest_ema_slow:
                        log_print(f"[DEBUG] Latest EMA20: {latest_ema_slow:.2f}")
                if rsi:
                    latest_rsi = next((x for x in reversed(rsi) if x is not None), None)
                    if latest_rsi:
                        log_print(f"[DEBUG] Latest RSI: {latest_rsi:.2f}")

                # Generate signal based on indicators
                if not closes or len(closes) < 2:
                    log_print(f"[DEBUG] {symbol}: Not enough price data for signal generation")
                    log_print(f"{sym}-EQ: ₹{ltp:,.2f}  Δ {delta_str}")
                    continue

                # Get latest values (skip None values at the beginning)
                def get_latest_valid(arr):
                    for i in range(len(arr)-1, -1, -1):
                        if arr[i] is not None:
                            return arr[i]
                    return None

                latest_close = get_latest_valid(closes)
                latest_ema_fast = get_latest_valid(ema_fast)
                latest_ema_slow = get_latest_valid(ema_slow)
                latest_rsi = get_latest_valid(rsi)
                latest_macd = get_latest_valid(macd_line)
                latest_signal = get_latest_valid(signal_line)
                latest_volume = get_latest_valid(volumes)
                latest_volume_ma = get_latest_valid(volume_ma)

                if None in [latest_close, latest_ema_fast, latest_ema_slow, latest_rsi,
                            latest_macd, latest_signal, latest_volume, latest_volume_ma]:
                    log_print(f"[DEBUG] {symbol}: Missing indicator data - close:{latest_close is not None}, ema_fast:{latest_ema_fast is not None}, ema_slow:{latest_ema_slow is not None}, rsi:{latest_rsi is not None}, macd:{latest_macd is not None}, signal:{latest_signal is not None}, volume:{latest_volume is not None}, volume_ma:{latest_volume_ma is not None}")
                    log_print(f"{sym}-EQ: ₹{ltp:,.2f}  Δ {delta_str}")
                    continue

                # Trend condition: Price above/below EMA20 (slow EMA)
                uptrend = latest_close > latest_ema_slow
                downtrend = latest_close < latest_ema_slow

                # Momentum condition: RSI not in extreme zones
                rsi_not_overbought = latest_rsi < RSI_OVERBOUGHT
                rsi_not_oversold = latest_rsi > RSI_OVERSOLD

                # MACD condition: Crossover
                # We need previous values to detect crossover
                macd_values = [x for x in macd_line if x is not None]
                signal_values = [x for x in signal_line if x is not None]

                if len(macd_values) < 2 or len(signal_values) < 2:
                    log_print(f"[DEBUG] {symbol}: Not enough MACD/signal values for crossover - macd:{len(macd_values)}, signal:{len(signal_values)}")
                    log_print(f"{sym}-EQ: ₹{ltp:,.2f}  Δ {delta_str}")
                    continue

                prev_macd = macd_values[-2]
                curr_macd = macd_values[-1]
                prev_signal = signal_values[-2]
                curr_signal = signal_values[-1]

                # Bullish crossover: MACD crosses above signal line
                bullish_cross = prev_macd <= prev_signal and curr_macd > curr_signal
                # Bearish crossover: MACD crosses below signal line
                bearish_cross = prev_macd >= prev_signal and curr_macd < curr_signal

                # Volume condition: Current volume above average
                volume_confirm = latest_volume > (latest_volume_ma * 1.2)  # 20% above average

                # Log detailed condition evaluation
                log_print(f"[DEBUG] {sym}: Signal evaluation - Close:{latest_close:.2f}, EMA20:{latest_ema_slow:.2f}, Uptrend:{uptrend}, Downtrend:{downtrend}")
                log_print(f"[DEBUG] {sym}: RSI:{latest_rsi:.2f}, Overbought(>{RSI_OVERBOUGHT}):{not rsi_not_overbought}, Oversold(<{RSI_OVERSOLD}):{not rsi_not_oversold}")
                log_print(f"[DEBUG] {sym}: MACD:{curr_macd:.4f}, Signal:{curr_signal:.4f}, Bullish Cross:{bullish_cross}, Bearish Cross:{bearish_cross}")
                log_print(f"[DEBUG] {sym}: Volume:{latest_volume:.0f}, Vol MA:{latest_volume_ma:.0f}, Vol Confirm ({latest_volume:.0f} > {latest_volume_ma * 1.2:.0f}):{volume_confirm}")

                # Prepare eligibility information
                eligibility_info = {
                    'uptrend': uptrend,
                    'downtrend': downtrend,
                    'rsi_not_overbought': rsi_not_overbought,
                    'rsi_not_oversold': rsi_not_oversold,
                    'bullish_cross': bullish_cross,
                    'bearish_cross': bearish_cross,
                    'volume_confirm': volume_confirm,
                    'latest_close': latest_close,
                    'latest_ema_slow': latest_ema_slow,
                    'latest_rsi': latest_rsi,
                    'latest_macd': curr_macd,
                    'latest_signal': curr_signal,
                    'latest_volume': latest_volume,
                    'latest_volume_ma': latest_volume_ma
                }

                # Generate signals
                if uptrend and rsi_not_overbought and bullish_cross and volume_confirm:
                    log_print(f"[SIGNAL] {sym}: BUY signal generated")
                    signal = "BUY"
                elif downtrend and rsi_not_oversold and bearish_cross and volume_confirm:
                    log_print(f"[SIGNAL] {sym}: SELL signal generated")
                    signal = "SELL"
                else:
                    log_print(f"[DEBUG] {sym}: No signal - Uptrend_Combo:{uptrend and rsi_not_overbought and bullish_cross and volume_confirm}, Downtrend_Combo:{downtrend and rsi_not_oversold and bearish_cross and volume_confirm}")
                    signal = None

                # Determine eligibility for summary
                is_eligible = (eligibility_info['uptrend'] and eligibility_info['rsi_not_overbought'] and
                             eligibility_info['bullish_cross'] and eligibility_info['volume_confirm']) or \
                            (eligibility_info['downtrend'] and eligibility_info['rsi_not_oversold'] and
                             eligibility_info['bearish_cross'] and eligibility_info['volume_confirm'])
                # Calculate entry and exit prices if we have a signal
                entry_price = None
                exit_price = None
                if signal == "BUY":
                    entry_price = ltp
                    exit_price = ltp * (1 - STOP_LOSS_PCT)  # Stop loss for long
                elif signal == "SELL":
                    entry_price = ltp
                    exit_price = ltp * (1 + STOP_LOSS_PCT)  # Stop loss for short
                # Collect data for summary table
                iteration_results.append({
                    'symbol': sym,
                    'ltp': ltp,
                    'change': delta,
                    'pct_change': delta_pct,
                    'volume': eligibility_info['latest_volume'],
                    'ema20': eligibility_info['latest_ema_slow'],
                    'rsi': eligibility_info['latest_rsi'],
                    'macd': eligibility_info['latest_macd'],
                    'signal': signal,
                    'vol_ma': eligibility_info['latest_volume_ma'],
                    'verdict': "YES" if is_eligible else "NO",
                    'entry_price': entry_price,
                    'exit_price': exit_price
                })

                # Log price and signal
                signal_str = f" [{signal}]" if signal else ""
                log_print(f"{sym}-EQ: ₹{ltp:,.2f}  Δ {delta_str}{signal_str}")

                # Log eligibility information
                if eligibility_info:
                    eligibility_details = []
                    # Trend
                    if eligibility_info['uptrend']:
                        eligibility_details.append("Uptrend")
                    elif eligibility_info['downtrend']:
                        eligibility_details.append("Downtrend")
                    else:
                        eligibility_details.append("No trend")
                    # RSI status
                    if eligibility_info['rsi_not_overbought'] and eligibility_info['rsi_not_oversold']:
                        eligibility_details.append(f"RSI:{eligibility_info['latest_rsi']:.1f}")
                    elif not eligibility_info['rsi_not_overbought']:
                        eligibility_details.append(f"RSI:{eligibility_info['latest_rsi']:.1f} (OB)")
                    else:
                        eligibility_details.append(f"RSI:{eligibility_info['latest_rsi']:.1f} (OS)")

                    # MACD crossover
                    if eligibility_info['bullish_cross']:
                        eligibility_details.append("MACD Bull Cross")
                    elif eligibility_info['bearish_cross']:
                        eligibility_details.append("MACD Bear Cross")
                    else:
                        eligibility_details.append("No MACD Cross")

                    # Volume confirmation
                    vol_status = "OK" if eligibility_info['volume_confirm'] else "Low"
                    eligibility_details.append(f"Vol {eligibility_info['latest_volume']:.0f} vs MA {eligibility_info['latest_volume_ma']:.0f} ({vol_status})")

                    eligibility_str = " | ".join(eligibility_details)

                    # Determine if eligible for trade (all conditions met)
                    is_eligible = (eligibility_info['uptrend'] and eligibility_info['rsi_not_overbought'] and
                                 eligibility_info['bullish_cross'] and eligibility_info['volume_confirm']) or \
                                (eligibility_info['downtrend'] and eligibility_info['rsi_not_oversold'] and
                                 eligibility_info['bearish_cross'] and eligibility_info['volume_confirm'])

                    trade_status = "UP FOR TRADING" if is_eligible else "NOT UP FOR TRADING"
                    log_print(f"[TRADING STATUS] {sym}-EQ: {trade_status}")

                    # Optional detailed eligibility breakdown
                    log_print(f"[DETAILS] {sym}-EQ: {eligibility_str}")

                # Handle signal
                if signal == "BUY" and sym not in positions:
                    open_position(sym, "BUY", ltp, api)
                elif signal == "SELL" and sym not in positions:
                    open_position(sym, "SELL", ltp, api)

            except Exception as exc:
                log_print(f"[WARN] {sym}-EQ: {exc}")

        # Send end scanning message to Telegram
        if TELEGRAM_ENABLED:
            end_time = time.time()
            elapsed_time = end_time - loop_start
            start_time_str = datetime.fromtimestamp(loop_start).strftime('%H:%M:%S')
            end_time_str = datetime.fromtimestamp(end_time).strftime('%H:%M:%S')

            # Filter for only symbols with signals
            signals = [r for r in iteration_results if r['signal'] in ['BUY', 'SELL']]

            telegram_message = f"📊 *Swing Bot Scan Completed*\n\n"
            telegram_message += f"• Started: {escape_telegram_text(start_time_str)}\n"
            telegram_message += f"• Ended: {escape_telegram_text(end_time_str)}\n"
            telegram_message += f"• Duration: {elapsed_time:.1f}s\n"
            telegram_message += f"• Scanned: {len(WATCH_LIST_INFO)} symbols\n"

            buy_count = sum(1 for s in signals if s['signal'] == 'BUY')
            sell_count = sum(1 for s in signals if s['signal'] == 'SELL')
            telegram_message += f"• Signals: {len(signals)} ({buy_count} BUY, {sell_count} SELL)"

            send_telegram_message(telegram_message)

        # Print summary table for this iteration
        if iteration_results:
            # Prepare the data for the table
            headers = ["Symbol", "LTP", "Change", "%Change", "Volume", "EMA20", "RSI", "MACD", "Signal", "Sell/Buy Call", "VolMA", "Verdict", "Entry", "Exit"]
            formatted_rows = []
            for r in iteration_results:
                entry_str = f"{r['entry_price']:.2f}" if r['entry_price'] is not None else "N/A"
                exit_str = f"{r['exit_price']:.2f}" if r['exit_price'] is not None else "N/A"
                formatted_rows.append([
                    r['symbol'],
                    f"{r['ltp']:.2f}",
                    f"{r['change']:+.2f}",
                    f"{r['pct_change']:+.2f}%",
                    f"{int(r['volume']):,}",
                    f"{r['ema20']:.2f}" if r['ema20'] is not None else "N/A",
                    f"{r['rsi']:.2f}" if r['rsi'] is not None else "N/A",
                    f"{r['macd']:.4f}" if r['macd'] is not None else "N/A",
                    r['signal'] if r['signal'] is not None else "N/A",
                    r['signal'] if r['signal'] is not None else "N/A",  # Sell/Buy Call column
                    f"{int(r['vol_ma']):,}" if r['vol_ma'] is not None else "N/A",
                    r['verdict'],
                    entry_str,
                    exit_str
                ])

            # Compute column widths
            col_widths = []
            for i in range(len(headers)):
                header_len = len(headers[i])
                max_cell_len = max(len(row[i]) for row in formatted_rows)
                col_widths.append(max(header_len, max_cell_len))

            # Define text columns (left-aligned) and numeric columns (right-aligned)
            text_col_indices = [0, 8, 9, 11]  # Symbol, Signal, Sell/Buy Call, and Verdict

            # Build separator line
            sep = "+"
            for w in col_widths:
                sep += "-" * (w + 2) + "+"

            # Build header line
            header_line = "|"
            for i, header in enumerate(headers):
                if i in text_col_indices:
                    header_line += f" {header:<{col_widths[i]}} |"
                else:
                    header_line += f" {header:>{col_widths[i]}} |"

            # Build each row line
            row_lines = []
            for row in formatted_rows:
                line = "|"
                for i, cell in enumerate(row):
                    if i in text_col_indices:
                        line += f" {cell:<{col_widths[i]}} |"
                    else:
                        line += f" {cell:>{col_widths[i]}} |"
                row_lines.append(line)

            # Build the full table string
            table_lines = [sep, header_line, sep] + row_lines + [sep]
            table_str = "\n".join(table_lines)

            # Log the table
            log_print("")
            log_print("Iteration Summary:")
            log_print(table_str)

        # Update existing positions
        update_positions(current_prices)

        # Log portfolio summary
        if positions:
            summary_parts = []
            for sym, pos in positions.items():
                if sym in current_prices:
                    current_price = current_prices[sym]
                    if pos['side'] == 'LONG':
                        unrealized_pct = ((current_price / pos['entry_price']) - 1) * 100
                    else:
                        unrealized_pct = ((pos['entry_price'] / current_price) - 1) * 100
                    summary_parts.append(f"{sym}: {pos['side']} {unrealized_pct:+.1f}%")

            if summary_parts:
                log_print(f"[PORTFOLIO] {' | '.join(summary_parts)}")

        # # Sleep until next interval
        # elapsed = time.time() - loop_start
        #
        # sleep_time = max(0, POLL_INTERVAL_SEC - elapsed)
        # time.sleep(sleep_time)

    finally:
        log_print("Shutting down…")
        # Close any remaining positions at market price (for reporting)
        if positions:
            log_print("[INFO] Closing all open positions for final report:")
            for sym, pos in list(positions.items()):
                if sym in current_prices:
                    close_price = current_prices[sym]
                    check_position_exits(sym, close_price)

        try:
            api.logout()
        except Exception:
            pass

        # Send shutdown message to Telegram
        if TELEGRAM_ENABLED:
            shutdown_message = "🛑 *Swing Bot Stopped*\n\n"
            shutdown_message += "The bot has been shut down gracefully.\n"
            shutdown_message += f"Final positions: {len(positions)} open"
            send_telegram_message(shutdown_message)

        log_print("Good‑bye!")

if __name__ == "__main__":
    # Override csv_file with command line argument if provided
    parser = argparse.ArgumentParser(description='Swing Trading Bot')
    parser.add_argument('--csv-file', type=str, default="ind_nifty50list.csv",
                        help='CSV file containing stock symbols (default: ind_nifty50list.csv)')
    args = parser.parse_args()
    csv_file = args.csv_file
    main(csv_file)