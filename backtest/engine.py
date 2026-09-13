"""
Backtesting engine for swing trading bot.
Processes historical data chronologically and simulates trades based on the strategy logic.
"""

import sys
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# Add project root to sys.path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backtest.data_loader import fetch_historical_data
from broker.yahoo_finance import get_historical_data_for_indicators
from strategy.swing_bot import (
    calculate_ema, calculate_rsi, calculate_macd,
    EMA_FAST, EMA_SLOW, RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL, VOLUME_MA_PERIOD,
    STOP_LOSS_PCT, TAKE_PROFIT_PCT, calculate_position_size
)


class BacktestEngine:
    """
    Core backtesting engine that simulates the swing trading strategy on historical data.
    """

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: Dict[str, Dict] = {}  # Current open positions
        self.trade_history: List[Dict] = []   # Completed trades
        self.equity_curve: List[float] = [initial_capital]  # Capital over time
        self.timestamps: List[str] = []       # Corresponding timestamps for equity curve
        self.signals_generated: int = 0       # Total signals generated (before position sizing)

    def run_backtest(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        timeframe: str = "1D"
    ) -> Dict:
        """
        Run backtest on multiple symbols over a date range.

        Args:
            symbols: List of stock symbols to backtest
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            timeframe: Data timeframe (1D, 1h, etc.)

        Returns:
            Dictionary containing trade history, equity curve, and performance metrics
        """
        print(f"[INFO] Starting backtest for {len(symbols)} symbols from {start_date} to {end_date}")
        print(f"[INFO] Timeframe: {timeframe}, Initial capital: ₹{self.initial_capital:,.2f}")

        # Fetch historical data for all symbols
        all_data = {}
        for symbol in symbols:
            print(f"[INFO] Fetching data for {symbol}...")
            data = fetch_historical_data(symbol, start_date, end_date, timeframe)
            if data:
                all_data[symbol] = data
                print(f"[INFO] Fetched {len(data)} candles for {symbol}")
            else:
                print(f"[WARN] No data found for {symbol}, skipping")

        if not all_data:
            print("[ERROR] No data available for any symbols")
            return {'trades': [], 'equity_curve': [], 'timestamps': []}

        # Determine the common timeline (use the symbol with most data as reference)
        reference_symbol = max(all_data.keys(), key=lambda s: len(all_data[s]))
        reference_data = all_data[reference_symbol]

        print(f"[INFO] Using {reference_symbol} as reference timeline ({len(reference_data)} data points)")

        # Process each timestamp chronologically
        for i, candle in enumerate(reference_data):
            timestamp = candle['timestamp']

            # Update equity curve with current capital
            self.equity_curve.append(self.current_capital)
            self.timestamps.append(timestamp)

            # Process each symbol at this timestamp
            for symbol in all_data.keys():
                # Find corresponding candle for this symbol at this timestamp
                symbol_candle = self._find_candle_at_time(all_data[symbol], timestamp)
                if not symbol_candle:
                    continue

                # Update existing positions
                self._update_positions(symbol, symbol_candle)

                # Check for new signals (only if no existing position)
                if symbol not in self.positions:
                    signal = self._generate_signal(symbol, all_data[symbol], i, timestamp)
                    if signal:
                        self.signals_generated += 1
                        self._open_position(symbol, signal, symbol_candle)

            # Progress indicator
            if i % 50 == 0 and i > 0:
                progress = (i / len(reference_data)) * 100
                print(f"[INFO] Progress: {progress:.1f}% ({i}/{len(reference_data)})")

        # Close any remaining positions at the end
        print("[INFO] Closing remaining positions at end of backtest...")
        if self.positions:
            last_candle = reference_data[-1]
            last_timestamp = last_candle['timestamp']
            for symbol in list(self.positions.keys()):
                if symbol in all_data:
                    symbol_candle = self._find_candle_at_time(all_data[symbol], last_timestamp)
                    if symbol_candle:
                        self._close_position(symbol, symbol_candle, last_timestamp, "END_OF_BACKTEST")

        print(f"[INFO] Backtest completed. Total trades: {len(self.trade_history)}")
        print(f"[INFO] Final capital: ₹{self.current_capital:,.2f}")

        return {
            'trades': self.trade_history,
            'equity_curve': self.equity_curve,
            'timestamps': self.timestamps,
            'signals_generated': self.signals_generated
        }

    def _find_candle_at_time(self, data: List[Dict], target_timestamp: str) -> Optional[Dict]:
        """
        Find candle data for a specific timestamp.
        Since we're processing chronologically, we look for exact match or closest previous.
        """
        # For simplicity in this backtest, we assume data is aligned
        # In a more sophisticated version, we'd handle different trading hours, etc.
        for candle in data:
            if candle['timestamp'] == target_timestamp:
                return candle
        # If exact match not found, return the most recent candle before target
        # This is a simplification - in reality we'd need better alignment
        for candle in reversed(data):
            if candle['timestamp'] <= target_timestamp:
                return candle
        return None

    def _generate_signal(self, symbol: str, data: List[Dict], current_index: int, timestamp: str) -> Optional[str]:
        """
        Generate trading signal based on strategy logic.
        Returns 'BUY', 'SELL', or None.
        """
        # Need enough data for indicators
        lookback = max(EMA_SLOW, RSI_PERIOD, MACD_SLOW, VOLUME_MA_PERIOD)
        if current_index < lookback:
            return None

        # Extract price and volume arrays up to current point
        slice_data = data[:current_index+1]
        closes = [c['close'] for c in slice_data]
        volumes = [c['volume'] for c in slice_data]

        # Calculate indicators
        ema_fast = calculate_ema(closes, EMA_FAST)
        ema_slow = calculate_ema(closes, EMA_SLOW)
        rsi = calculate_rsi(closes, RSI_PERIOD)
        macd_line, signal_line, _ = calculate_macd(closes, MACD_FAST, MACD_SLOW, MACD_SIGNAL)

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
        latest_signal_val = get_latest_valid(signal_line)
        latest_volume = get_latest_valid(volumes)
        latest_volume_ma = get_latest_valid(volume_ma)

        # Check if we have all required values
        if None in [latest_close, latest_ema_fast, latest_ema_slow, latest_rsi,
                    latest_macd, latest_signal_val, latest_volume, latest_volume_ma]:
            return None

        # Trend condition: Price above/below EMA20 (slow EMA) but not too extended
        trend_distance = 0.01  # 1% maximum extension from EMA
        uptrend = latest_close > latest_ema_slow and latest_close < latest_ema_slow * (1 + trend_distance)
        downtrend = latest_close < latest_ema_slow and latest_close > latest_ema_slow * (1 - trend_distance)

        # Momentum condition: RSI not in extreme zones
        rsi_not_overbought = latest_rsi < RSI_OVERBOUGHT
        rsi_not_oversold = latest_rsi > RSI_OVERSOLD

        # MACD condition: Crossover
        macd_values = [x for x in macd_line if x is not None]
        signal_values = [x for x in signal_line if x is not None]

        if len(macd_values) < 2 or len(signal_values) < 2:
            return None

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

        # Generate signals
        if uptrend and rsi_not_overbought and bullish_cross and volume_confirm:
            return "BUY"
        elif downtrend and rsi_not_oversold and bearish_cross and volume_confirm:
            return "SELL"
        else:
            return None

    def _open_position(self, symbol: str, signal: str, candle: Dict):
        """
        Open a new position based on signal.
        """
        entry_price = candle['close']
        quantity = calculate_position_size(entry_price)

        if quantity <= 0:
            return

        if signal == "BUY":
            stop_loss = entry_price * (1 - STOP_LOSS_PCT)
            take_profit = entry_price * (1 + TAKE_PROFIT_PCT)
            position_side = "LONG"
        else:  # SELL
            stop_loss = entry_price * (1 + STOP_LOSS_PCT)
            take_profit = entry_price * (1 - TAKE_PROFIT_PCT)
            position_side = "SHORT"

        self.positions[symbol] = {
            'symbol': symbol,
            'side': position_side,
            'entry_price': entry_price,
            'quantity': quantity,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_time': candle['timestamp'],
            'signal_type': signal  # BUY or SELL
        }

        # Record trade opening (we'll complete it on exit)
        # For now, just store in positions

    def _update_positions(self, symbol: str, candle: Dict):
        """
        Update existing positions and check for exit conditions.
        """
        if symbol not in self.positions:
            return

        position = self.positions[symbol]
        current_price = candle['close']
        timestamp = candle['timestamp']

        exit_price = None
        exit_reason = None

        # Check stop loss and take profit
        if position['side'] == 'LONG':
            if current_price <= position['stop_loss']:
                exit_price = position['stop_loss']
                exit_reason = "STOP_LOSS"
            elif current_price >= position['take_profit']:
                exit_price = position['take_profit']
                exit_reason = "TAKE_PROFIT"
        else:  # SHORT
            if current_price >= position['stop_loss']:
                exit_price = position['stop_loss']
                exit_reason = "STOP_LOSS"
            elif current_price <= position['take_profit']:
                exit_price = position['take_profit']
                exit_reason = "TAKE_PROFIT"

        # If exit condition met, close position
        if exit_price is not None:
            self._close_position(symbol, candle, timestamp, exit_reason, exit_price)

    def _close_position(
        self,
        symbol: str,
        candle: Dict,
        timestamp: str,
        exit_reason: str,
        exit_price: Optional[float] = None
    ):
        """
        Close an existing position and record the trade.
        """
        if symbol not in self.positions:
            return

        position = self.positions[symbol]
        if exit_price is None:
            exit_price = candle['close']

        # Calculate P&L
        if position['side'] == 'LONG':
            pnl = (exit_price - position['entry_price']) * position['quantity']
            pnl_pct = ((exit_price / position['entry_price']) - 1) * 100
        else:  # SHORT
            pnl = (position['entry_price'] - exit_price) * position['quantity']
            pnl_pct = ((position['entry_price'] / exit_price) - 1) * 100

        # Record completed trade
        trade_record = {
            'symbol': symbol,
            'action': position['signal_type'],  # Original signal (BUY/SELL)
            'position_side': position['side'],
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'quantity': position['quantity'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'entry_time': position['entry_time'],
            'exit_time': timestamp,
            'exit_reason': exit_reason,
            'duration_hours': self._calculate_duration(
                position['entry_time'], timestamp
            )
        }

        self.trade_history.append(trade_record)

        # Update capital
        self.current_capital += pnl

        # Remove from open positions
        del self.positions[symbol]

    def _calculate_duration(self, start_time: str, end_time: str) -> float:
        """
        Calculate duration between two timestamps in hours.
        """
        try:
            fmt = "%Y-%m-%d %H:%M"
            start = datetime.strptime(start_time, fmt)
            end = datetime.strptime(end_time, fmt)
            return (end - start).total_seconds() / 3600
        except:
            return 0.0

    def get_performance_summary(self) -> Dict:
        """
        Get a summary of backtest performance.
        """
        from backtest.metrics import calculate_metrics, calculate_trade_durations

        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'final_capital': self.current_capital,
                'total_return_pct': 0.0
            }

        metrics = calculate_metrics(self.trade_history, self.initial_capital)
        avg_duration, median_duration = calculate_trade_durations(self.trade_history)

        summary = {
            'total_trades': metrics['total_trades'],
            'win_rate': metrics['win_rate'],
            'profit_factor': metrics['profit_factor'],
            'sharpe_ratio': metrics['sharpe_ratio'],
            'max_drawdown': metrics['max_drawdown'],
            'total_return_pct': metrics['total_return_pct'],
            'final_capital': self.current_capital,
            'avg_trade_duration_hours': avg_duration,
            'median_trade_duration_hours': median_duration
        }

        return summary


def run_backtest(
    symbols: List[str],
    start_date: str,
    end_date: str,
    timeframe: str = "1D",
    initial_capital: float = 100000.0
) -> Dict:
    """
    Convenience function to run a backtest.

    Args:
        symbols: List of stock symbols
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        timeframe: Data timeframe
        initial_capital: Starting capital

    Returns:
        Dictionary with results
    """
    engine = BacktestEngine(initial_capital)
    return engine.run_backtest(symbols, start_date, end_date, timeframe)


if __name__ == "__main__":
    # Test the backtesting engine
    print("Testing backtesting engine...")

    # Test with a small dataset
    result = run_backtest(
        symbols=["RELIANCE"],
        start_date="2026-06-01",
        end_date="2026-06-30",
        timeframe="1D",
        initial_capital=100000.0
    )

    trades = result['trades']
    print(f"Backtest completed. Generated {len(trades)} trades.")

    if trades:
        print("\nSample trades:")
        for i, trade in enumerate(trades[:3]):  # Show first 3 trades
            print(f"Trade {i+1}: {trade['symbol']} {trade['action']} "
                  f"Entry: ₹{trade['entry_price']:.2f} -> Exit: ₹{trade['exit_price']:.2f} "
                  f"P&L: ₹{trade['pnl']:.2f} ({trade['pnl_pct']:.2f}%)")