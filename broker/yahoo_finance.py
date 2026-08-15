import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time

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

    def get_top_nse_performers(self, limit: int = 100, criteria: str = "percent_change") -> List[Dict]:
        """
        Get top NSE performers based on daily percentage change.
        Returns list of dicts with symbol data compatible with swing_bot.py expectations.
        """
        try:
            # Nifty 50 stocks with .NS suffix for yfinance
            nifty_50_symbols = [
                "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "APOLLOTYRE.NS", "ASIANPAINT.NS",
                "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BAJAJHLDNG.NS",
                "BEL.NS", "BHARTIARTL.NS", "BIOCON.NS", "BPCL.NS", "BRITANNIA.NS", "CIPLA.NS",
                "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS", "EICHERMOT.NS", "GAIL.NS", "GRASIM.NS",
                "HCLTECH.NS", "HDFC.NS", "HDFCBANK.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HAL.NS",
                "HINDUNILVR.NS", "ICICIBANK.NS", "INDUSINDBK.NS", "INFY.NS", "IOC.NS", "ITC.NS",
                "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS", "LTIM.NS", "M&M.NS", "MARUTI.NS", "NESTLEIND.NS",
                "NTPC.NS", "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHREECEM.NS",
                "SHRIRAMFIN.NS", "SUNPHARMA.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS",
                "TCS.NS", "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "UPL.NS", "WIPRO.NS"
            ]

            # Fetch data for last 2 days to calculate change
            data = yf.download(nifty_50_symbols, period="2d", progress=False)

            if data.empty:
                # Fallback to just returning symbols with zero change if download fails
                results = []
                for symbol in nifty_50_symbols[:limit]:
                    base_symbol = symbol.replace(".NS", "")
                    results.append({
                        "symbol": base_symbol,
                        "exchange": "NSE",
                        "symboltoken": "0",  # Dummy token
                        "ltp": 0.0,
                        "change": 0.0,
                        "percent_change": 0.0,
                        "volume": 0,
                        "value": 0.0
                    })
                return results

            # Calculate daily change percentage for each stock
            results = []
            for symbol in nifty_50_symbols:
                base_symbol = symbol.replace(".NS", "")
                try:
                    # Get last 2 closing prices
                    if len(data['Close']) >= 2 and symbol in data['Close'].columns:
                        close_prices = data['Close'][symbol].dropna()
                        if len(close_prices) >= 2:
                            yesterday_close = close_prices.iloc[-2]
                            today_close = close_prices.iloc[-1]

                            if yesterday_close != 0:
                                change = today_close - yesterday_close
                                percent_change = (change / yesterday_close) * 100
                            else:
                                change = 0.0
                                percent_change = 0.0

                            # Get volume (if available)
                            volume = 0
                            if 'Volume' in data.columns and symbol in data['Volume'].columns:
                                vol_data = data['Volume'][symbol].dropna()
                                if not vol_data.empty:
                                    volume = int(vol_data.iloc[-1])

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
                except Exception as e:
                    # If calculation fails for a stock, add it with zero values
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
                    continue

            # Sort by percent_change descending (top gainers first)
            if criteria.lower() in ("percent_change", "percentchange", "pct_change"):
                results.sort(key=lambda x: x['percent_change'], reverse=True)
            # For other criteria, we could implement different sorting, but default to percent_change

            return results[:limit]

        except Exception as e:
            # Ultimate fallback - return basic Nifty 50 list
            print(f"[WARN] Yahoo Finance top performers fetch failed: {e}")
            results = []
            for symbol in nifty_50_symbols[:limit]:
                base_symbol = symbol.replace(".NS", "")
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
            return results

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