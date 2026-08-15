# Fix Summary: Telegram Signal Detection Bug

## 🐞 The Issue
The Telegram message was showing "0 eligible for trade" even when signals were present because:
- In the `iteration_results` dictionary, the `'signal'` field was incorrectly storing the **MACD signal line value** (a float) instead of the **trading signal** ("BUY"/"SELL"/None)
- When filtering for signals with `r['signal'] in ['BUY', 'SELL']`, it was comparing floats to strings, which never matched
- This resulted in an empty `signals` list, causing the "0 eligible for trade" message

## 🔧 The Fix
**File:** `strategy/swing_bot.py`  
**Line:** 672

**Changed from:**
```python
'signal': eligibility_info['latest_signal'],
```

**Changed to:**
```python
'signal': signal,
```

## ✅ Why This Works
- The `signal` variable (lines 638-646) correctly holds:
  - `"BUY"` when bullish conditions are met
  - `"SELL"` when bearish conditions are met  
  - `None` when no signal is present
- Storing this actual trading signal in `iteration_results` allows the filter `r['signal'] in ['BUY', 'SELL']` to work correctly
- The MACD signal line value is still stored in the `'macd'` field for reference in the table

## 📱 Expected Behavior Now
When signals are present, the Telegram END message will show:
```
📊 *Swing Bot Scan Completed*

• Started: 13:08:38
• Ended: 13:09:20
• Duration: 42.6s
• Scanned: 42 symbols
• Signals: 2 (1 BUY, 1 SELL)

📈 RELIANCE: BUY
   Entry: ₹2,500.00
   SL: ₹2,450.00 (-2.0%)
   TP: ₹2,600.00 (+4.0%)
   RSI: 58.2 | Vol: 2,45,678
```

Instead of the incorrect:
```
📊 *Swing Bot Scan Completed*

• Started: 13:08:38
• Ended: 13:09:20
• Duration: 42.6s
• Scanned: 42 symbols
• Signals: 0 eligible for trade
```

## 🧪 Verified
- Syntax check: ✅ No errors
- Import test: ✅ Module loads successfully
- Telegram enabled: ✅ Confirmed from logs