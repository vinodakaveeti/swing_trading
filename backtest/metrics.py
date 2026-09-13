"""
Performance metrics calculator for backtesting module.
Calculates various trading performance statistics from trade history.
"""

import numpy as np
from typing import List, Dict, Tuple
from datetime import datetime


def calculate_metrics(trades: List[Dict], initial_capital: float = 100000.0) -> Dict[str, float]:
    """
    Calculate performance metrics from a list of trades.

    Args:
        trades: List of trade dictionaries with keys:
                'symbol', 'action', 'entry_price', 'exit_price',
                'quantity', 'pnl', 'pnl_pct', 'entry_time', 'exit_time'
        initial_capital: Starting capital for calculations

    Returns:
        Dictionary of performance metrics
    """
    if not trades:
        return {
            'total_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'total_return_pct': 0.0,
            'avg_trade_pct': 0.0,
            'avg_win_pct': 0.0,
            'avg_loss_pct': 0.0,
            'expectancy': 0.0,
            'total_fees': 0.0
        }

    # Extract P&L percentages
    pnl_pcts = [trade['pnl_pct'] for trade in trades]

    # Separate wins and losses
    wins = [p for p in pnl_pcts if p > 0]
    losses = [p for p in pnl_pcts if p < 0]

    # Basic stats
    total_trades = len(trades)
    win_rate = len(wins) / total_trades if total_trades > 0 else 0.0

    # Profit factor
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf') if gross_profit > 0 else 0.0

    # Average trade P&L
    avg_trade_pct = np.mean(pnl_pcts) if pnl_pcts else 0.0
    avg_win_pct = np.mean(wins) if wins else 0.0
    avg_loss_pct = np.mean(losses) if losses else 0.0

    # Expectancy
    expectancy = (win_rate * avg_win_pct) + ((1 - win_rate) * avg_loss_pct)

    # Calculate equity curve for drawdown and Sharpe ratio
    equity_curve = [initial_capital]
    for trade in trades:
        equity_curve.append(equity_curve[-1] + trade['pnl'])

    # Calculate returns series (daily approximation)
    returns = []
    for i in range(1, len(equity_curve)):
        ret = (equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
        returns.append(ret)

    # Sharpe ratio (simplified - assuming 0% risk-free rate, 252 trading days/year)
    if returns and np.std(returns) > 0:
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)
    else:
        sharpe_ratio = 0.0

    # Maximum drawdown
    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    max_drawdown_pct = max_drawdown * 100

    # Total return
    total_return_pct = ((equity_curve[-1] - initial_capital) / initial_capital) * 100

    return {
        'total_trades': total_trades,
        'win_rate': win_rate * 100,  # Convert to percentage
        'profit_factor': profit_factor,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown_pct,
        'total_return_pct': total_return_pct,
        'avg_trade_pct': avg_trade_pct,
        'avg_win_pct': avg_win_pct,
        'avg_loss_pct': avg_loss_pct,
        'expectancy': expectancy,
        'total_return': equity_curve[-1] - initial_capital
    }


def calculate_trade_durations(trades: List[Dict]) -> Tuple[float, float]:
    """
    Calculate average and median trade durations.

    Args:
        trades: List of trade dictionaries with 'entry_time' and 'exit_time'

    Returns:
        Tuple of (average_duration_hours, median_duration_hours)
    """
    if not trades:
        return 0.0, 0.0

    durations = []
    for trade in trades:
        try:
            entry_time = datetime.strptime(trade['entry_time'], "%Y-%m-%d %H:%M:%S")
            exit_time = datetime.strptime(trade['exit_time'], "%Y-%m-%d %H:%M:%S")
            duration_hours = (exit_time - entry_time).total_seconds() / 3600
            durations.append(duration_hours)
        except:
            # If time parsing fails, skip this trade for duration calc
            continue

    if not durations:
        return 0.0, 0.0

    avg_duration = np.mean(durations)
    median_duration = np.median(durations)

    return avg_duration, median_duration


def calculate_monthly_returns(trades: List[Dict], initial_capital: float = 100000.0) -> Dict[str, float]:
    """
    Calculate monthly returns from trade history.

    Args:
        trades: List of trade dictionaries
        initial_capital: Starting capital

    Returns:
        Dictionary mapping 'YYYY-MM' to monthly return percentage
    """
    if not trades:
        return {}

    # Sort trades by exit time
    sorted_trades = sorted(trades, key=lambda x: x['exit_time'])

    # Build equity curve by date
    equity_by_date = {}
    current_equity = initial_capital

    for trade in sorted_trades:
        exit_date = trade['exit_time'].split()[0]  # Extract date part
        if exit_date not in equity_by_date:
            equity_by_date[exit_date] = current_equity
        current_equity += trade['pnl']
        equity_by_date[exit_date] = current_equity

    # Calculate monthly returns
    monthly_returns = {}
    dates = sorted(equity_by_date.keys())

    for i in range(1, len(dates)):
        prev_date = dates[i-1]
        curr_date = dates[i]

        # Extract year-month
        prev_ym = prev_date[:7]  # YYYY-MM
        curr_ym = curr_date[:7]  # YYYY-MM

        if prev_ym not in monthly_returns:
            monthly_returns[prev_ym] = 0.0

        prev_equity = equity_by_date[prev_date]
        curr_equity = equity_by_date[curr_date]

        if prev_equity != 0:
            monthly_ret = (curr_equity - prev_equity) / prev_equity * 100
            monthly_returns[prev_ym] += monthly_ret  # Accumulate if multiple trades in month

    return monthly_returns


if __name__ == "__main__":
    # Test the metrics calculator
    print("Testing metrics calculator...")

    # Sample trade data
    sample_trades = [
        {
            'symbol': 'RELIANCE',
            'action': 'BUY',
            'entry_price': 2500.0,
            'exit_price': 2600.0,
            'quantity': 40,
            'pnl': 4000.0,
            'pnl_pct': 4.0,
            'entry_time': '2026-06-01 10:00:00',
            'exit_time': '2026-06-05 15:00:00'
        },
        {
            'symbol': 'TCS',
            'action': 'SELL',
            'entry_price': 3500.0,
            'exit_price': 3400.0,
            'quantity': 30,
            'pnl': 3000.0,
            'pnl_pct': 2.86,
            'entry_time': '2026-06-10 09:30:00',
            'exit_time': '2026-06-12 14:15:00'
        },
        {
            'symbol': 'INFY',
            'action': 'BUY',
            'entry_price': 1500.0,
            'exit_price': 1450.0,
            'quantity': 70,
            'pnl': -3500.0,
            'pnl_pct': -3.33,
            'entry_time': '2026-06-20 11:00:00',
            'exit_time': '2026-06-22 16:45:00'
        }
    ]

    metrics = calculate_metrics(sample_trades)
    print("Metrics calculated:")
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

    avg_dur, median_dur = calculate_trade_durations(sample_trades)
    print(f"Average trade duration: {avg_dur:.2f} hours")
    print(f"Median trade duration: {median_dur:.2f} hours")