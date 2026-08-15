#!/usr/bin/env python3
"""
Yahoo Finance NSE Data Fetcher
---------------------------
This script demonstrates how to use the yfinance package to fetch
NSE (National Stock Exchange) stock data including:
- Stock names and symbols
- Last Traded Price (LTP)
- Top gainers/losers
- Historical data

This is completely separate from your existing Angel One-based swing_bot.py
and does not modify any existing files.

Requirements:
    pip install yfinance pandas

Usage:
    python3 yahoo_finance_nse.py
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

def get_nifty_50_symbols():
    """
    Returns a list of Nifty 50 stock symbols with .NS suffix for yfinance
    Note: yfinance uses .NS suffix for NSE stocks
    """
    nifty_50 = [
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
    return nifty_50

def get_stock_ltp(symbol):
    """
    Get Last Traded Price (LTP) for a single stock
    """
    try:
        ticker = yf.Ticker(symbol)
        # Get recent data (1 day period to get latest price)
        data = ticker.history(period="1d")
        if not data.empty:
            ltp = data['Close'].iloc[-1]
            return ltp
        else:
            return None
    except Exception as e:
        print(f"Error fetching LTP for {symbol}: {e}")
        return None

def get_multiple_stocks_ltp(symbols):
    """
    Get LTP for multiple stocks efficiently
    """
    try:
        # Download data for all symbols at once
        data = yf.download(symbols, period="1d", progress=False)
        if data.empty:
            return {}

        # Extract closing prices (LTP)
        ltp_data = {}
        if len(symbols) == 1:
            # Single stock case
            ltp_data[symbols[0]] = data['Close'].iloc[-1] if not data['Close'].empty else None
        else:
            # Multiple stocks case
            for symbol in symbols:
                if symbol in data['Close'].columns:
                    ltp_data[symbol] = data['Close'][symbol].iloc[-1] if not data['Close'][symbol].empty else None
                else:
                    ltp_data[symbol] = None

        return ltp_data
    except Exception as e:
        print(f"Error fetching multiple stocks data: {e}")
        return {}

def get_top_gainers_losers(limit=10):
    """
    Attempt to get top gainers and losers from NSE
    Note: yfinance doesn't have a direct "top gainers" endpoint,
    so we'll calculate based on daily change for Nifty 50 stocks
    """
    print(f"Fetching data for top {limit} gainers and losers from Nifty 50...")
    symbols = get_nifty_50_symbols()

    # Get data for last 2 days to calculate change
    try:
        data = yf.download(symbols, period="2d", progress=False)
        if data.empty:
            print("No data downloaded")
            return [], []

        # Calculate daily change percentage
        changes = {}
        for symbol in symbols:
            try:
                if len(data['Close']) >= 2 and symbol in data['Close'].columns:
                    close_prices = data['Close'][symbol].dropna()
                    if len(close_prices) >= 2:
                        yesterday_close = close_prices.iloc[-2]
                        today_close = close_prices.iloc[-1]
                        change_pct = ((today_close - yesterday_close) / yesterday_close) * 100
                        changes[symbol] = change_pct
            except Exception as e:
                print(f"Error calculating change for {symbol}: {e}")
                continue

        # Sort by change percentage
        sorted_changes = sorted(changes.items(), key=lambda x: x[1], reverse=True)

        top_gainers = sorted_changes[:limit]
        top_losers = sorted_changes[-limit:]
        top_losers.reverse()  # Show most negative first

        return top_gainers, top_losers
    except Exception as e:
        print(f"Error fetching top gainers/losers: {e}")
        return [], []

def get_stock_info(symbol):
    """
    Get comprehensive info for a single stock
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        # Extract relevant information
        stock_data = {
            'symbol': symbol.replace('.NS', ''),
            'name': info.get('longName', 'N/A'),
            'ltp': info.get('regularMarketPrice', 'N/A'),
            'change': info.get('regularMarketChange', 'N/A'),
            'change_percent': info.get('regularMarketChangePercent', 'N/A'),
            'volume': info.get('regularMarketVolume', 'N/A'),
            'market_cap': info.get('marketCap', 'N/A'),
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A')
        }
        return stock_data
    except Exception as e:
        print(f"Error fetching info for {symbol}: {e}")
        return None

def display_nifty_50_status():
    """
    Display current status of Nifty 50 stocks
    """
    print("\n" + "="*80)
    print("NIFTY 50 STOCKS - CURRENT STATUS")
    print("="*80)

    symbols = get_nifty_50_symbols()
    print(f"Fetching LTP for {len(symbols)} Nifty 50 stocks...")

    ltp_data = get_multiple_stocks_ltp(symbols)

    if not ltp_data:
        print("Failed to fetch stock data")
        return

    # Prepare data for display
    display_data = []
    for symbol, ltp in ltp_data.items():
        clean_symbol = symbol.replace('.NS', '')
        if ltp is not None:
            display_data.append({
                'Symbol': clean_symbol,
                'LTP (₹)': f"{ltp:.2f}"
            })
        else:
            display_data.append({
                'Symbol': clean_symbol,
                'LTP (₹)': 'N/A'
            })

    # Display in a nice format
    df = pd.DataFrame(display_data)
    print(df.to_string(index=False))
    print(f"\nSuccessfully fetched data for {len([d for d in display_data if d['LTP (₹)'] != 'N/A'])} stocks")

def display_top_movers():
    """
    Display top gainers and losers
    """
    print("\n" + "="*80)
    print("TOP MOVERS IN NIFTY 50 (Based on Daily Change)")
    print("="*80)

    top_gainers, top_losers = get_top_gainers_losers(limit=5)

    if top_gainers:
        print("\nTOP 5 GAINERS:")
        print("-" * 50)
        for symbol, change_pct in top_gainers:
            clean_symbol = symbol.replace('.NS', '')
            print(f"{clean_symbol:12} : {change_pct:+.2f}%")
    else:
        print("\nUnable to fetch top gainers data")

    if top_losers:
        print("\nTOP 5 LOSERS:")
        print("-" * 50)
        for symbol, change_pct in top_losers:
            clean_symbol = symbol.replace('.NS', '')
            print(f"{clean_symbol:12} : {change_pct:+.2f}%")
    else:
        print("\nUnable to fetch top losers data")

def get_historical_data(symbol, period="1mo"):
    """
    Get historical data for a stock
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        return hist
    except Exception as e:
        print(f"Error fetching historical data for {symbol}: {e}")
        return None

def main():
    """
    Main function demonstrating various yfinance capabilities for NSE stocks
    """
    print("YAHOO FINANCE NSE DATA FETCHER")
    print("="*50)
    print("This script demonstrates how to fetch NSE stock data using yfinance")
    print("Completely separate from your existing Angel One-based swing_bot.py\n")

    # Example 1: Get Nifty 50 symbols
    print("1. Nifty 50 Symbols (first 10):")
    symbols = get_nifty_50_symbols()
    print(f"   {', '.join([s.replace('.NS', '') for s in symbols[:10]])}...")
    print(f"   Total: {len(symbols)} symbols\n")

    # Example 2: Get LTP for a single stock
    print("2. Single Stock LTP Example (RELIANCE):")
    reliance_ltp = get_stock_ltp("RELIANCE.NS")
    if reliance_ltp:
        print(f"   RELIANCE LTP: ₹{reliance_ltp:.2f}\n")
    else:
        print("   Failed to fetch RELIANCE LTP\n")

    # Example 3: Get LTP for multiple stocks
    print("3. Multiple Stocks LTP Example (Top 5 Nifty 50):")
    sample_symbols = symbols[:5]
    multi_ltp = get_multiple_stocks_ltp(sample_symbols)
    for symbol, ltp in multi_ltp.items():
        clean_symbol = symbol.replace('.NS', '')
        if ltp is not None:
            print(f"   {clean_symbol}: ₹{ltp:.2f}")
        else:
            print(f"   {clean_symbol}: N/A")
    print()

    # Example 4: Get stock info
    print("4. Detailed Stock Info Example (TCS):")
    tcs_info = get_stock_info("TCS.NS")
    if tcs_info:
        print(f"   Name: {tcs_info['name']}")
        print(f"   LTP: ₹{tcs_info['ltp']}")
        print(f"   Change: {tcs_info['change']} ({tcs_info['change_percent']}%)")
        print(f"   Volume: {tcs_info['volume']:,}")
        print(f"   Sector: {tcs_info['sector']}")
        print(f"   Industry: {tcs_info['industry']}\n")
    else:
        print("   Failed to fetch TCS info\n")

    # Example 5: Display Nifty 50 status
    display_nifty_50_status()

    # Example 6: Display top movers
    display_top_movers()

    # Example 7: Historical data example
    print("\n" + "="*80)
    print("HISTORICAL DATA EXAMPLE (RELIANCE - Last 1 Month)")
    print("="*80)
    hist_data = get_historical_data("RELIANCE.NS", period="1mo")
    if hist_data is not None and not hist_data.empty:
        print(f"   Data points: {len(hist_data)}")
        print(f"   Date range: {hist_data.index[0].date()} to {hist_data.index[-1].date()}")
        print(f"   Latest close: ₹{hist_data['Close'].iloc[-1]:.2f}")
        print(f"   Period change: {((hist_data['Close'].iloc[-1] / hist_data['Close'].iloc[0]) - 1) * 100:+.2f}%")
    else:
        print("   Failed to fetch historical data")

    print("\n" + "="*80)
    print("DEMO COMPLETE")
    print("="*80)
    print("\nTo use this in your trading strategy:")
    print("1. Install yfinance: pip install yfinance pandas")
    print("2. Import yfinance in your code: import yfinance as yf")
    print("3. Use yf.Ticker('SYMBOL.NS') to get stock data")
    print("4. Use .history() for historical data")
    print("5. Use .info for detailed stock information")
    print("\nNote: All NSE stock symbols in yfinance require '.NS' suffix")

if __name__ == "__main__":
    main()