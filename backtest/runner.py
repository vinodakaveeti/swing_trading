"""
CLI runner for the swing trading backtesting module.
Provides command-line interface for running backtests.
"""

import argparse
import sys
import os
from datetime import datetime
from typing import List

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backtest.data_loader import fetch_historical_data, get_available_symbols
from backtest.engine import run_backtest
from backtest.report import generate_report, save_report


def main():
    parser = argparse.ArgumentParser(
        description="Backtest the swing trading strategy on historical data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backtest.runner --symbol RELIANCE --timeframe 1D --start 2026-01-01 --end 2026-06-30
  python -m backtest.runner --symbols RELIANCE TCS INFY --timeframe 1D --start 2026-01-01 --end 2026-06-30
  python -m backtest.runner --symbol RELIANCE --timeframe 1h --start "2026-08-31 10:00:00" --end "2026-08-31 12:00:00"
  python -m backtest.runner --list-symbols
        """
    )

    parser.add_argument(
        '--symbol', '-s',
        type=str,
        help='Single stock symbol to backtest (e.g., RELIANCE)'
    )

    parser.add_argument(
        '--symbols',
        type=str,
        nargs='+',
        help='Multiple stock symbols to backtest (e.g., RELIANCE TCS INFY)'
    )

    parser.add_argument(
        '--timeframe', '-t',
        type=str,
        default='1D',
        choices=['5m', '15m', '30m', '1h', '1d', 'FIVE_MINUTE', 'FIFTEEN_MINUTE', 'THIRTY_MINUTE', 'ONE_HOUR', 'ONE_DAY'],
        help='Data timeframe (default: 1D)'
    )

    parser.add_argument(
        '--start',
        type=str,
        help='Start date/time in YYYY-MM-DD or YYYY-MM-DD HH:MM:SS format'
    )

    parser.add_argument(
        '--end',
        type=str,
        help='End date/time in YYYY-MM-DD or YYYY-MM-DD HH:MM:SS format'
    )

    parser.add_argument(
        '--capital',
        type=float,
        default=100000.0,
        help='Initial capital in INR (default: 100000)'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file to save report (optional)'
    )

    parser.add_argument(
        '--list-symbols',
        action='store_true',
        help='List available symbols for backtesting'
    )

    args = parser.parse_args()

    # Handle list symbols request
    if args.list_symbols:
        print("Available symbols for backtesting:")
        symbols = get_available_symbols()
        for i, symbol in enumerate(symbols, 1):
            print(f"  {i:2d}. {symbol}")
        return

    # Validate arguments
    if not args.symbol and not args.symbols:
        print("[ERROR] Please specify either --symbol or --symbols")
        parser.print_help()
        return

    if args.symbol and args.symbols:
        print("[ERROR] Please specify either --symbol or --symbols, not both")
        return

    # Validate that start and end dates are provided when not listing symbols
    if not args.start or not args.end:
        print("[ERROR] --start and --end are required when running a backtest")
        parser.print_help()
        return

    # Determine symbols to test
    symbols = []
    if args.symbol:
        symbols = [args.symbol.upper()]
    else:
        symbols = [s.upper() for s in args.symbols]

    # Validate date/time format
    def parse_datetime(date_str):
        """Parse date string that may include time component."""
        try:
            # Try parsing with time component first
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                # Try parsing date only
                return datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Invalid date/time format: {date_str}")

    try:
        start_date = parse_datetime(args.start)
        end_date = parse_datetime(args.end)
        if start_date >= end_date:
            print("[ERROR] Start date/time must be before end date/time")
            return
    except ValueError as e:
        print(f"[ERROR] {e}")
        print("[INFO] Use format: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS")
        return

    # Adjust timeframe format
    timeframe_map = {
        'FIVE_MINUTE': '5m',
        'FIFTEEN_MINUTE': '15m',
        'THIRTY_MINUTE': '30m',
        'ONE_HOUR': '1h',
        'ONE_DAY': '1d'
    }
    timeframe = timeframe_map.get(args.timeframe, args.timeframe)

    print(f"[INFO] Starting backtest...")
    print(f"[INFO] Symbols: {', '.join(symbols)}")
    print(f"[INFO] Timeframe: {timeframe}")
    print(f"[INFO] Period: {args.start} to {args.end}")
    print(f"[INFO] Initial Capital: ₹{args.capital:,.2f}")
    print()

    # Run backtest
    try:
        result = run_backtest(
            symbols=symbols,
            start_date=args.start,
            end_date=args.end,
            timeframe=timeframe,
            initial_capital=args.capital
        )

        trades = result['trades']
        equity_curve = result['equity_curve']
        timestamps = result['timestamps']

        # Generate report
        symbol_str = ", ".join(symbols)
        report = generate_report(
            trades=trades,
            equity_curve=equity_curve,
            timestamps=timestamps,
            initial_capital=args.capital,
            symbol=symbol_str,
            timeframe=args.timeframe,  # Use original format for display
                signals_generated=result.get('signals_generated', 0),
            start_date=args.start,
            end_date=args.end
        )

        # Print report
        print(report)

        # Save report if requested
        if args.output:
            save_report(report, args.output)

    except Exception as e:
        print(f"[ERROR] Backtest failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()