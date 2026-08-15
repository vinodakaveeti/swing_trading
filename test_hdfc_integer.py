#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from broker.angel_one import AngelOneAPI

def test_symbol_with_integer_token(symbol):
    print(f"Testing symbol {symbol} with integer token")
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

    # Try with token as integer
    try:
        token_as_int = int(info["symboltoken"])
        print(f"Trying with token as integer: {token_as_int}")
        ltp = api.get_ltp(info["exchange"], f"{symbol}-EQ", token_as_int)
        print(f"SUCCESS! LTP: {ltp}")
    except Exception as e:
        print(f"FAILED with integer token: {e}")

    # Try with token as string (original)
    try:
        print(f"Trying with token as string: {info['symboltoken']}")
        ltp = api.get_ltp(info["exchange"], f"{symbol}-EQ", info["symboltoken"])
        print(f"SUCCESS! LTP: {ltp}")
    except Exception as e:
        print(f"FAILED with string token: {e}")

    try:
        api.logout()
    except:
        pass

if __name__ == "__main__":
    test_symbol_with_integer_token("HDFC")