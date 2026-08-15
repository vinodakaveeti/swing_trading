import yfinance as yf
from datetime import datetime
from typing import Dict, List, Optional
import csv
import os
import re

class YahooFinanceAPI:
    """
    Yahoo Finance API wrapper for NSE stock data.
    Provides similar interface to AngelOneAPI for use with swing_bot.py
    """
    def __init__(self):
        # No credentials needed for basic yfinance
        self.last_login_time = None

    def login(self) -> bool:
        """No login required for yfinance - always returns True"""
        self.last_login_time = datetime.now()
        return True

    def logout(self) -> None:
        """No logout required for yfinance"""
        self.last_login_time = None

    def get_ltp(self, exchange: str, tradingsymbol: str, symboltoken: str) -> float:
        """
        Get Last Traded Price for a symbol.
        Note: exchange and symboltoken parameters are ignored for yfinance compatibility,
        but we extract the base symbol from tradingsymbol (expects format like "RELIANCE-EQ")
        """
        try:
            # Extract base symbol from tradingsymbol (e.g., "RELIANCE-EQ" -> "RELIANCE")
            if tradingsymbol.endswith("-EQ"):
                base_symbol = tradingsymbol[:-3]
            else:
                base_symbol = tradingsymbol

            # Add .NS suffix for NSE stocks in yfinance
            yf_symbol = f"{base_symbol}.NS"

            ticker = yf.Ticker(yf_symbol)
            # Get current price - try fast_info first, then fallback to history
            try:
                fast_info = ticker.fast_info
                if hasattr(fast_info, 'last_price') and fast_info.last_price:
                    return float(fast_info.last_price)
            except:
                pass

            # Fallback to recent history
            hist = ticker.history(period="1d")
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
            else:
                raise Exception(f"No price data available for {yf_symbol}")

        except Exception as e:
            raise Exception(f"Failed to get LTP for {tradingsymbol}: {e}")

    def get_top_nse_performers(self, limit: int = 50, criteria: str = "percent_change", csv_file: str = None) -> List[Dict]:
        """
        Get top NSE performers based on daily percentage change.
        Reads equity list from specified CSV file and fetches details for each symbol.
        Returns list of dicts with symbol data compatible with swing_bot.py expectations.
        """
        # Set default CSV file if none provided
        if csv_file is None:
            csv_file = "/Users/vinodakaveeti/Desktop/Projects/swing_trading/ind_nifty50list.csv"

        # Ensure the path is relative to the project root if not absolute
        if not os.path.isabs(csv_file):
            csv_path = os.path.join("/Users/vinodakaveeti/Desktop/Projects/swing_trading", csv_file)
        else:
            csv_path = csv_file

        # Extract limit from filename if csv_file matches pattern ind_nifty{number}list.csv
        effective_limit = limit  # Default to provided limit
        if csv_file is not None:
            # Extract filename from path
            filename = os.path.basename(csv_file)
            # Match pattern: ind_nifty{number}list.csv
            match = re.match(r'ind_nifty(\d+)list\.csv$', filename, re.IGNORECASE)
            if match:
                try:
                    extracted_limit = int(match.group(1))
                    # Use extracted limit if it's reasonable (between 1 and 10000)
                    if 1 <= extracted_limit <= 10000:
                        effective_limit = extracted_limit
                except ValueError:
                    pass  # Keep effective_limit as the parameter limit if conversion fails

        try:
            # Read symbols from CSV
            symbols = []
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    symbol = row.get('SYMBOL')
                    if symbol:
                        symbols.append(symbol.strip())
            if not symbols:
                raise ValueError("No symbols found in CSV")

            # Prepare yfinance symbols
            yf_symbols = [f"{s}.NS" for s in symbols]

            # Fetch data for last 2 days
            data = yf.download(yf_symbols, period="2d", progress=False)

            results = []
            if not data.empty:
                # We have data for multiple symbols
                for symbol in symbols:
                    yf_symbol = f"{symbol}.NS"
                    base_symbol = symbol
                    try:
                        # Check if we have data for this symbol
                        if ('Close' in data and yf_symbol in data['Close'].columns and
                            len(data['Close'][yf_symbol].dropna()) >= 2):
                            close_series = data['Close'][yf_symbol].dropna()
                            yesterday_close = close_series.iloc[-2]
                            today_close = close_series.iloc[-1]

                            if yesterday_close != 0:
                                change = today_close - yesterday_close
                                percent_change = (change / yesterday_close) * 100
                            else:
                                change = 0.0
                                percent_change = 0.0

                            # Volume
                            volume = 0
                            if ('Volume' in data and yf_symbol in data['Volume'].columns and
                                len(data['Volume'][yf_symbol].dropna()) > 0):
                                vol_series = data['Volume'][yf_symbol].dropna()
                                volume = int(vol_series.iloc[-1])

                            results.append({
                                "symbol": base_symbol,
                                "exchange": "NSE",
                                "symboltoken": "0",  # Dummy token
                                "ltp": float(today_close),
                                "change": float(change),
                                "percent_change": float(percent_change),
                                "volume": volume,
                                "value": float(today_close * volume) if volume > 0 else 0.0
                            })
                        else:
                            # Not enough data, fallback to zero
                            raise ValueError("Insufficient data")
                    except Exception as e:
                        # If calculation fails, add with zero values
                        results.append({
                            "symbol": base_symbol,
                            "exchange": "NSE",
                            "symboltoken": "0",
                            "ltp": 0.0,
                            "change": 0.0,
                            "percent_change": 0.0,
                            "volume": 0,
                            "value": 0.0
                        })
            else:
                # Download failed, try fetching symbol by symbol
                for symbol in symbols:
                    base_symbol = symbol
                    yf_symbol = f"{symbol}.NS"
                    try:
                        ticker = yf.Ticker(yf_symbol)
                        # Get last 2 days of data
                        hist = ticker.history(period="2d")
                        if hist.empty or len(hist) < 2:
                            raise ValueError("Not enough data")

                        close_series = hist['Close']
                        yesterday_close = close_series.iloc[-2]
                        today_close = close_series.iloc[-1]

                        if yesterday_close != 0:
                            change = today_close - yesterday_close
                            percent_change = (change / yesterday_close) * 100
                        else:
                            change = 0.0
                            percent_change = 0.0

                        volume = 0
                        if 'Volume' in hist.columns and not hist['Volume'].empty:
                            volume = int(hist['Volume'].iloc[-1])

                        results.append({
                            "symbol": base_symbol,
                            "exchange": "NSE",
                            "symboltoken": "0",
                            "ltp": float(today_close),
                            "change": float(change),
                            "percent_change": float(percent_change),
                            "volume": volume,
                            "value": float(today_close * volume) if volume > 0 else 0.0
                        })
                    except Exception as e:
                        results.append({
                            "symbol": base_symbol,
                            "exchange": "NSE",
                            "symboltoken": "0",
                            "ltp": 0.0,
                            "change": 0.0,
                            "percent_change": 0.0,
                            "volume": 0,
                            "value": 0.0
                        })

            # Sort by percent_change descending (top gainers first)
            if criteria.lower() in ("percent_change", "percentchange", "pct_change"):
                results.sort(key=lambda x: x['percent_change'], reverse=True)
            # For other criteria, we could implement different sorting, but default to percent_change

            return results[:effective_limit]

        except Exception as e:
            # Fallback: return empty list to let caller handle fallback
            print(f"[WARN] Yahoo Finance top performers fetch from CSV failed: {e}")
            return []

    def symbol_lookup(self, symbol: str) -> Dict:
        """
        Look up symbol information.
        For Yahoo Finance compatibility, we return basic info.
        Note: The actual symbol resolution happens in get_ltp using the .NS suffix convention.
        """
        # Return dummy but valid values - the actual trading symbol construction happens elsewhere
        return {
            "exchange": "NSE",
            "symbol": f"{symbol}-EQ",  # This is what swing_bot.py expects
            "symboltoken": "0"  # Dummy token - not actually used by yfinance methods
        }

# Helper function to get historical data in the format expected by swing_bot.py's indicators
def get_historical_data_for_indicators(symbol: str, interval: str = "FIVE_MINUTE", lookback_periods: int = 50) -> Optional[List[Dict]]:
    """
    Fetch historical candle data in the format expected by swing_bot.py's technical indicators.
    This replaces the get_historical_data function in swing_bot.py when using Yahoo Finance.
    """
    try:
        # Convert symbol to yfinance format (e.g., "RELIANCE" -> "RELIANCE.NS")
        yf_symbol = f"{symbol}.NS"

        # Map interval to yfinance format
        interval_map = {
            "FIVE_MINUTE": "5m",
            "FIFTEEN_MINUTE": "15m",
            "THIRTY_MINUTE": "30m",
            "ONE_HOUR": "1h",
            "ONE_DAY": "1d"
        }
        yf_interval = interval_map.get(interval, "5m")

        # Calculate period needed - yfinance limits intraday data to last 30 days
        # We'll request enough data to cover our lookback period plus buffer
        if yf_interval in ["5m", "15m", "30m"]:
            # For intraday, request 5 days of data to ensure we have enough candles
            period = "5d"
        elif yf_interval == "1h":
            period = "30d"  # Max for 1h interval
        else:  # 1d
            period = "60d"  # Enough for ~2 months of daily data

        # Download data
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period=period, interval=yf_interval)

        if hist.empty:
            return None

        # Convert to the format expected by swing_bot.py indicators function
        # Expected: list of dicts with keys: timestamp, open, high, low, close, volume
        candles = []
        for timestamp, row in hist.iterrows():
            # Format timestamp to match swing_bot.py expectation: "%Y-%m-%d %H:%M"
            # yfinance gives us timezone-aware datetime, we'll make it naive and format
            if hasattr(timestamp, 'tz_localize'):
                # Remove timezone info for formatting
                dt = timestamp.tz_localize(None) if timestamp.tz is not None else timestamp
            else:
                dt = timestamp

            timestamp_str = dt.strftime("%Y-%m-%d %H:%M")

            candles.append({
                'timestamp': timestamp_str,
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': float(row['Volume'])
            })

        # Return the most recent 'lookback_periods' candles
        if len(candles) > lookback_periods:
            return candles[-lookback_periods:]
        else:
            return candles

    except Exception as e:
        print(f"[WARN] Failed to get historical data for {symbol}: {e}")
        return None


if __name__ == "__main__":
    yahoo_obj = YahooFinanceAPI()
    print(yahoo_obj.get_top_nse_performers())