#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from broker.angel_one import AngelOneAPI

def test_symbol(symbol):
    print(f"Testing symbol: {symbol}")
    api = AngelOneAPI()
    try:
        print("Logging in...")
        api.login()
        print("Login successful.")
    except Exception as e:
        print(f"Login failed: {e}")
        return False

    try:
        print(f"Looking up symbol {symbol}...")
        info = api.symbol_lookup(symbol)
        print(f"Symbol info: {info}")

        print(f"Getting LTP for {symbol}...")
        ltp = api.get_ltp(
            exchange=info["exchange"],
            tradingsymbol=info["symbol"],
            symboltoken=info["symboltoken"]
        )
        print(f"LTP for {symbol}: {ltp}")
        return True
    except Exception as e:
        print(f"Error getting LTP for {symbol}: {e}")
        return False
    finally:
        try:
            api.logout()
        except:
            pass

if __name__ == "__main__":
    symbols = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HDFC", "SBIN"]
    for symbol in symbols:
        print(f"\n{'='*50}")
        success = test_symbol(symbol)
        print(f"Result for {symbol}: {'SUCCESS' if success else 'FAILED'}")
        print('='*50)