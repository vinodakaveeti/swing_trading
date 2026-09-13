"""
Historical data loader for backtesting module.
Fetches and prepares historical data for backtesting the swing trading strategy.
"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd


def fetch_historical_data(
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str = "1D"
) -> Optional[List[Dict]]:
    """
    Fetch historical data for a symbol within a date/time range.

    Args:
        symbol: Stock symbol (e.g., "RELIANCE")
        start_date: Start date/time in YYYY-MM-DD or YYYY-MM-DD HH:MM:SS format
        end_date: End date/time in YYYY-MM-DD or YYYY-MM-DD HH:MM:SS format
        timeframe: Data timeframe (5m, 15m, 30m, 1h, 1d)

    Returns:
        List of dictionaries with OHLCV data or None if failed
    """
    try:
        # Convert symbol to yfinance format
        yf_symbol = f"{symbol}.NS"

        # Map timeframe to yfinance interval
        interval_map = {
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "1d": "1d",
            "FIVE_MINUTE": "5m",
            "FIFTEEN_MINUTE": "15m",
            "THIRTY_MINUTE": "30m",
            "ONE_HOUR": "1h",
            "ONE_DAY": "1d"
        }

        yf_interval = interval_map.get(timeframe, "1d")

        # Parse start and end datetime strings
        def parse_datetime_str(date_str):
            try:
                # Try parsing with time component first
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    # Try parsing with minutes only
                    return datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    # Try parsing date only
                    return datetime.strptime(date_str, "%Y-%m-%d")

        start_dt = parse_datetime_str(start_date)
        end_dt = parse_datetime_str(end_date)

        if start_dt >= end_dt:
            print("[ERROR] Start date/time must be before end date/time")
            return None

        # For data fetching, we need to use date-only strings for yfinance history()
        # but add a buffer to ensure we capture the full time range
        # Convert to date strings for yfinance (it doesn't accept time components in start/end)
        start_date_for_yf = start_dt.strftime("%Y-%m-%d")
        end_date_for_yf = end_dt.strftime("%Y-%m-%d")

        # Add buffer days to ensure we capture the time range properly
        # For intraday data, we might need to fetch extra days
        buffer_days = 0
        if yf_interval in ["5m", "15m", "30m"]:
            buffer_days = 2  # Need extra buffer for intraday due to yfinance limitations
        elif yf_interval == "1h":
            buffer_days = 1
        else:  # daily
            buffer_days = 1

        # Calculate the date range for yfinance request
        start_date_yf = (start_dt - timedelta(days=buffer_days)).strftime("%Y-%m-%d")
        end_date_yf = (end_dt + timedelta(days=buffer_days)).strftime("%Y-%m-%d")

        # Download data using date-only strings (which yfinance accepts)
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(start=start_date_yf, end=end_date_yf, interval=yf_interval)

        if hist.empty:
            print(f"[WARN] No data found for {symbol} from {start_date} to {end_date}")
            return None

        # Convert to the format expected by backtesting engine
        candles = []
        for timestamp, row in hist.iterrows():
            # Format timestamp to match expected format: "%Y-%m-%d %H:%M"
            if hasattr(timestamp, 'tz_localize'):
                # Remove timezone info for formatting
                dt = timestamp.tz_localize(None) if timestamp.tz is not None else timestamp
            else:
                dt = timestamp

            timestamp_str = dt.strftime("%Y-%m-%d %H:%M")

            # Convert string back to datetime for comparison
            candle_dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M")

            # Filter to only include candles within the requested time range
            if start_dt <= candle_dt < end_dt:
                candles.append({
                    'timestamp': timestamp_str,
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': float(row['Volume'])
                })

        if not candles:
            print(f"[WARN] No data found for {symbol} in the requested time range {start_date} to {end_date}")
            return None

        return candles

    except Exception as e:
        print(f"[ERROR] Failed to fetch historical data for {symbol}: {e}")
        return None


def get_available_symbols() -> List[str]:
    """
    Get list of available symbols from Nifty indices (placeholder).
    In a real implementation, this could read from CSV files or fetch from API.
    """
    # For now, return a sample list - in practice, this would come from your CSV files
    return [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
        "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "ASIANPAINT",
        "AXISBANK", "BAJFINANCE", "BAJAJFINSV", "HCLTECH", "WIPRO",
        "MARUTI", "TATAMOTORS", "SUNPHARMA", "M&M", "NTPC"
    ]


if __name__ == "__main__":
    # Test the data loader
    print("Testing historical data loader...")
    data = fetch_historical_data("RELIANCE", "2026-06-01", "2026-06-30", "1D")
    if data:
        print(f"Successfully fetched {len(data)} candles for RELIANCE")
        if data:
            print(f"First candle: {data[0]}")
            print(f"Last candle: {data[-1]}")
    else:
        print("Failed to fetch data")