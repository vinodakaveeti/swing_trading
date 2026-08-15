# Telegram Message Shortened - Summary

## 📱 User Request
The user wanted a shorter Telegram message that only shows the scan completion statistics without the detailed signal list.

**Requested format:**
```
📊 *Swing Bot Scan Completed*

• Started: 13:18:09
• Ended: 13:18:59
• Duration: 50.8s
• Scanned: 42 symbols
• Signals: 9 (6 BUY, 3 SELL)
```

## 🔧 Changes Made

**File:** `strategy/swing_bot.py`  
**Lines:** 736-782 (END message section)

**Simplified the END message to only show:**
- Scan start time (HH:MM:SS)
- Scan end time (HH:MM:SS)  
- Duration (seconds with 1 decimal)
- Number of symbols scanned
- Signal count with BUY/SELL breakdown

**Removed:**
- Detailed signal listing (BUY/SELL stocks with entry, SL, TP, RSI, Volume)
- "_and X more signals_" note
- Extra formatting and spacing

## ✅ Benefits
1. **Much shorter messages** - Well under Telegram's 4096-character limit
2. **Clean and concise** - Just the essential scan statistics
3. **Fast to read** - Users can quickly see scan performance
4. **Still informative** - Shows scan timing, coverage, and signal results
5. **Preserves all functionality** - Signal detection and local logging unchanged

## 📊 Example Output
When signals are found:
```
📊 *Swing Bot Scan Completed*

• Started: 13:18:09
• Ended: 13:18:59
• Duration: 50.8s
• Scanned: 42 symbols
• Signals: 9 (6 BUY, 3 SELL)
```

When no signals are found:
```
📊 *Swing Bot Scan Completed*

• Started: 13:18:09
• Ended: 13:18:59
• Duration: 50.8s
• Scanned: 42 symbols
• Signals: 0 (0 BUY, 0 SELL)
```

## ⚙️ Technical Notes
- The START message (at beginning of scan) remains unchanged
- Local console/table logging remains unchanged for detailed analysis
- All signal detection logic and strategy parameters remain intact
- Only the END Telegram message formatting was simplified