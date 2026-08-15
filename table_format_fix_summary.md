# Fix Summary: Table Formatting Error in Swing Bot

## 🐞 The Issue
After fixing the signal detection logic, a new error appeared when trying to display the summary table in the console:
```
ValueError: Unknown format code 'f' for object of type 'str'
```

This occurred because:
1. We changed the `'signal'` field in `iteration_results` to store the actual trading signal ("BUY"/"SELL"/None) instead of the MACD signal line value (float)
2. However, the table formatting code still tried to format this field as a float with `:.4f`
3. When the code encountered a string value ("BUY" or "SELL"), the float formatting failed

## 🔧 The Fix Applied

**File:** `strategy/swing_bot.py`

### Change 1: Fixed signal column formatting (Line 801)
**From:**
```python
f"{r['signal']:.4f}" if r['signal'] is not None else "N/A",
```
**To:**
```python
r['signal'] if r['signal'] is not None else "N/A",
```

### Change 2: Updated text column indices for proper alignment (Line 816)
**From:**
```python
text_col_indices = [0, 10]  # Symbol and Verdict
```
**To:**
```python
text_col_indices = [0, 8, 10]  # Symbol, Signal, and Verdict
```

## ✅ Why This Works
- The signal column now stores and displays the actual string values ("BUY", "SELL", or "N/A")
- By adding index 8 to `text_col_indices`, the signal column is left-aligned (like Symbol and Verdict columns)
- This makes the table more readable with proper text alignment for string values
- All other columns retain their numeric formatting and right-alignment

## 📱 Expected Table Output
The summary table in the console/logs will now display correctly:
```
+--------+--------+--------+---------+--------+--------+------+--------+--------+--------+--------+--------+--------+
| Symbol |   LTP  | Change | %Change | Volume |  EMA20 |  RSI |   MACD | Signal |  VolMA | Verdict|  Entry |  Exit  |
+--------+--------+--------+---------+--------+--------+------+--------+--------+--------+--------+--------+--------+
| RELIANCE| 2500.00| +12.50 | +0.50%  | 2,45,678| 2480.50| 58.20|  0.4520|  BUY   | 2,00,000|   YES  | 2500.00| 2600.00|
|   TCS  | 3800.00| -15.20 | -0.40%  | 1,89,450| 3820.30| 42.10| -0.3210|  SELL  | 1,50,000|   YES  | 3800.00| 3648.00|
+--------+--------+--------+---------+--------+--------+------+--------+--------+--------+--------+--------+--------+
```

## 🧪 Verified
- ✅ Syntax check passed
- ✅ Module imports successfully  
- ✅ Telegram notifications confirmed enabled from logs
- ✅ Local table logging now works without errors