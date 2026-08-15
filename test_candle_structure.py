#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from broker.angel_one import AngelOneAPI
from datetime import datetime, timedelta

def test_candle_data():
    print("Testing candle data structure...")
    api = AngelOneAPI()
    try:
        print("Logging in...")
        api.login()
        print("Login successful.")
    except Exception as e:
        print(f"Login failed: {e}")
        return

    # Get HDFCBANK symbol info
    try:
        info = api.symbol_lookup("HDFCBANK")
        print(f"Symbol info: {info}")

        # Try to get candle data for the last few hours
        # Format: YYYY-MM-DD HH:MM
        to_date = datetime.now()
        from_date = to_date - timedelta(hours=4)

        from_date_str = from_date.strftime("%Y-%m-%d %H:%M")
        to_date_str = to_date.strftime("%Y-%m-%d %H:%M")

        print(f"Fetching candles from {from_date_str} to {to_date_str}")

        candle_params = {
            "exchange": info["exchange"],
            "symboltoken": info["symboltoken"],
            "interval": "FIVE_MINUTE",  # Trying 5 minute interval
            "fromdate": from_date_str,
            "todate": to_date_str
        }

        print(f"Request params: {candle_params}")
        candle_data = api.smart.getCandleData(candle_params)
        print(f"Candle data response: {candle_data}")

        if candle_data.get("status") and candle_data.get("data"):
            print(f"Number of candles: {len(candle_data['data'])}")
            if candle_data['data']:
                print(f"First candle: {candle_data['data'][0]}")
                print(f"Last candle: {candle_data['data'][-1]}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            api.logout()
        except:
            pass

if __name__ == "__main__":
    test_candle_data()