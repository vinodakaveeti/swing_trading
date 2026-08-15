#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from broker.angel_one import AngelOneAPI

def test_symbol_variations(symbol):
    print(f"Testing symbol variations for: {symbol}")
    api = AngelOneAPI()
    try:
        print("Logging in...")
        api.login()
        print("Login successful.")
    except Exception as e:
        print(f"Login failed: {e}")
        return

    # Get the base symbol info from our map
    info = api.symbol_lookup(symbol)
    print(f"From our map: {info}")

    # Try different variations
    variations = [
        # Original from map
        (info["exchange"], f"{symbol}-EQ", info["symboltoken"]),
        # Try without -EQ
        (info["exchange"], symbol, info["symboltoken"]),
        # Try with different suffixes
        (info["exchange"], f"{symbol}-EQ", "12345"),  # dummy token to see error
        # Try BSE instead of NSE
        ("BSE", f"{symbol}-EQ", info["symboltoken"]),
        # Try NSE with different symbol format
        ("NSE", f"{symbol}.EQ", info["symboltoken"]),
        ("NSE", f"{symbol} EQ", info["symboltoken"]),
    ]

    for exchange, tradingsymbol, symboltoken in variations:
        print(f"\nTrying: exchange={exchange}, tradingsymbol={tradingsymbol}, symboltoken={symboltoken}")
        try:
            ltp = api.get_ltp(exchange, tradingsymbol, symboltoken)
            print(f"SUCCESS! LTP: {ltp}")
        except Exception as e:
            print(f"FAILED: {e}")

    try:
        api.logout()
    except:
        pass

if __name__ == "__main__":
    test_symbol_variations("HDFC")