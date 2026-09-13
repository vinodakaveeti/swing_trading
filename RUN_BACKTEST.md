# How to Run Swing Trading Backtests

## Quick Start

Run a backtest on Nifty 50 stocks using the command:

```bash
python -m backtest.runner --symbols $(cut -d, -f3 ind_nifty50list.csv | tail -n +2) --start 2024-01-01 --end 2026-08-15 --timeframe ONE_DAY
```

## Command Options

### Basic Usage
- `--symbol` or `-s`: Single stock (e.g., `--symbol RELIANCE`)
- `--symbols`: Multiple stocks (e.g., `--symbols RELIANCE TCS INFY`)
- `--timeframe` or `-t`: Timeframe (5m, 15m, 30m, 1h, 1d, or aliases like ONE_DAY)
- `--start`: Start date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
- `--end`: End date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
- `--capital`: Initial capital in INR (default: 100000)
- `--output` or `-o`: Save report to file (optional)
- `--list-symbols`: List available stocks

### Examples
```bash
# Single stock, daily timeframe
python -m backtest.runner --symbol RELIANCE --start 2024-01-01 --end 2026-08-15 --timeframe ONE_DAY

# Multiple stocks, hourly timeframe
python -m backtest.runner --symbols RELIANCE TCS INFY --start 2024-01-01 --end 2026-08-15 --timeframe ONE_HOUR

# Save report to file
python -m backtest.runner --symbols RELIANCE TCS --start 2024-01-01 --end 2026-08-15 --timeframe ONE_DAY --output my_backtest_report.txt

# List all available stocks
python -m backtest.runner --list-symbols
```

## Backtest Result Files

### 1. `current_params_nifty50.txt`
- **Parameters**: EMA=20/50, MACD=19/39, Stop Loss=1.0%, Take Profit=4.0%
- **Period**: 2024-01-01 to 2026-08-15 (ONE_DAY)
- **Results**: 48 trades, **+4.92%** return, 25.00% win rate
- **Performance**: Profit Factor 1.32, Expectancy +0.24%/trade

### 2. `params_100pct_nifty50.txt`
- **Parameters**: EMA=30/70, MACD=24/52, Stop Loss=2.0%, Take Profit=4.0%
- **Period**: 2024-01-01 to 2026-08-15 (ONE_DAY)
- **Results**: 36 trades, **-8.83%** return, 25.00% win rate
- **Performance**: Profit Factor 0.69, Expectancy -0.46%/trade

### 3. `github_params_test.txt`
- **Parameters**: EMA=12/26, MACD=12/26, Stop Loss=2.0%, Take Profit=4.0% (GitHub/main branch)
- **Test**: 3 symbols (ADANIENT, ADANIPORTS, APOLLOHOSP)
- **Results**: 1 trade, -0.97% return, 0.00% win rate

## Strategy Parameters Location

The strategy parameters are configured in:
`strategy/swing_bot.py`

To test different parameters, modify these values in the file:
- `EMA_FAST`, `EMA_SLOW`
- `MACD_FAST`, `MACD_SLOW` 
- `STOP_LOSS_PCT`, `TAKE_PROFIT_PCT`
- `RSI_PERIOD`, `RSI_OVERBOUGHT`, `RSI_OVERSOLD`

## Important Notes

1. **Data Source**: Uses Yahoo Finance (requires internet connection)
2. **Timeframe Formats**: 
   - Code aliases: FIVE_MINUTE, FIFTEEN_MINUTE, THIRTY_MINUTE, ONE_HOUR, ONE_DAY
   - Alternative formats: 5m, 15m, 30m, 1h, 1d
3. **Symbol Format**: Use NSE symbols without .NS suffix (e.g., RELIANCE, not RELIANCE.NS)
4. **Initial Capital**: Default ₹100,000, adjustable with --capital flag
5. **Output**: Prints detailed report to console, optionally saves to file with --output

## Interpreting Results

Key metrics in the backtest report:
- **Total Return**: Overall percentage gain/loss
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross profit / gross loss (>1.0 is profitable)
- **Expectancy**: Average profit/loss per trade
- **Max Drawdown**: Largest peak-to-trough decline
- **Trade List**: Individual trade details with entry/exit prices and P&L

## Troubleshooting

- **No data received**: Check symbol spelling, internet connection, or try different date range
- **Timeout on large datasets**: Test with fewer symbols or shorter date ranges first
- **Parameter changes not taking effect**: Ensure you're editing the correct strategy/swing_bot.py file