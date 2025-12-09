# 🎯 ORB Breakout Scanner - Complete Trading System

A comprehensive multi-asset Opening Range Breakout scanner that monitors stocks, indices, metals, and futures for real-time trading signals. Based on your TradingView Pine Script indicators with proper 2:1 Risk/Reward management.

## 📋 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Scanner Modes](#scanner-modes)
- [Strategy Explained](#strategy-explained)
- [Live Trading](#live-trading)
- [Backtesting](#backtesting)
- [Notifications Setup](#notifications-setup)
- [Files Guide](#files-guide)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

---

## 🌟 Overview

This system replicates your TradingView ORB strategy in Python, providing real-time monitoring, instant alerts, backtesting, and professional risk management.

### What is ORB Strategy?

**Opening Range Breakout** captures the first 15 minutes (9:30-9:45 AM) and trades breakouts:

1. **Capture OR** - Record high/low of 9:30-9:45 AM
2. **Wait for Breakout** - Price closes 2+ points beyond OR
3. **Enter on Retest** - Price pulls back to OR midpoint
4. **2:1 Risk/Reward** - Stop at OR boundary, target is 2× risk

### Features

✅ Multi-Asset Monitoring (15+ symbols)  
✅ Real-Time Alerts (Telegram/Email/Web)  
✅ Two Alert Modes (Breakout or Retest)  
✅ Backtesting with Performance Metrics  
✅ 2:1 Risk/Reward Auto-Calculated  
✅ State Management (no duplicate signals)  
✅ Diagnostic Tools (analyze signals)  

---

## 🚀 Quick Start

### 1. Install
```bash
pip install -r requirements.txt
```

### 2. Choose Mode

**Option A: Breakout Alert** (Get alerted when breakout occurs)
```bash
py orb_breakout_alerts.py
```

**Option B: Retest Signal** (Get alerted when retest occurs)
```bash
py orb_scanner_notifications.py
```

**Option C: Web Dashboard** (Visual monitoring)
```bash
py orb_web_dashboard.py
```
Then open: http://localhost:5000

### 3. Customize Watchlist

Edit any scanner file:
```python
SYMBOLS = [
    'SPY', 'QQQ', 'DIA',  # Indices
    'AAPL', 'TSLA',       # Stocks
    'GLD', 'SLV',         # Metals
]
```

---

## 📦 Installation

### Requirements
- Python 3.8+
- Internet connection
- Windows/Mac/Linux

### Steps

1. **Download files**

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify:**
   ```bash
   py test_backtest.py
   ```

4. **Optional: Setup Telegram**
   - Message [@BotFather](https://t.me/BotFather) → `/newbot`
   - Get bot token
   - Message [@userinfobot](https://t.me/userinfobot)
   - Get chat ID
   - Add to scanner files

---

## 🎮 Scanner Modes

### Mode 1: Breakout Alert 🔔 (NEW!)

**File:** `orb_breakout_alerts.py`

Alerts you WHEN breakout occurs, you watch for retest manually.

**Example Alert:**
```
🔼 BREAKOUT ALERT - SPY

Breakout Price: $683.50
Entry Level: $682.30 (watch for this!)
Stop Loss: $681.63
Target: $683.64

⏰ Monitor for pullback to midpoint!
```

**Best for:** Active traders watching charts

**Run:**
```bash
py orb_breakout_alerts.py
```

---

### Mode 2: Retest Signal 🎯

**File:** `orb_scanner_notifications.py`

Alerts you when retest occurs - enter immediately.

**Example Alert:**
```
🟢 ORB LONG SIGNAL

Symbol: SPY
Entry: $682.30 (NOW!)
Stop: $681.63
Target: $683.64
```

**Best for:** Busy traders, high-probability signals only

**Run:**
```bash
py orb_scanner_notifications.py
```

---

### Mode 3: Web Dashboard 🌐

**File:** `orb_web_dashboard.py`

Beautiful browser interface with live updates.

**Features:**
- Live status of all symbols
- Browser notifications
- Signal history
- Mobile-friendly

**Run:**
```bash
py orb_web_dashboard.py
```
Open: http://localhost:5000

---

### Mode Comparison

| Feature | Breakout Mode | Retest Mode | Dashboard |
|---------|---------------|-------------|-----------|
| **Alert Timing** | On breakout | On retest | Visual |
| **Signals/Week** | 4-8 | 0-5 | Monitor |
| **Entry** | Manual watch | Immediate | Manual |
| **Best For** | Active | Busy | Visual |

---

## 📚 Strategy Explained

### Entry Rules

**LONG:**
1. Price closes above OR High + 2 points
2. Price pulls back to OR Midpoint
3. Enter at midpoint

**SHORT:**
1. Price closes below OR Low - 2 points  
2. Price rallies to OR Midpoint
3. Enter at midpoint

### Risk Management

**LONG Example:**
```
OR High: $595.00
OR Mid:  $594.50  ← Entry
OR Low:  $594.00  ← Stop

Risk = $0.50
Target = Entry + (Risk × 2) = $595.50
R:R = 2:1
```

**Why 2:1?**
- 50% win rate = breakeven
- 60% win rate = profitable
- Professional standard

---

## 💰 Live Trading

### Daily Workflow

**Before 9:30 AM:**
```bash
py orb_breakout_alerts.py
```

**9:30-9:45 AM:**
- Scanner captures OR
- Logs: "SPY OR Captured - High: X, Low: Y"

**After 9:45 AM:**
- Monitors for breakouts
- Sends alerts when triggered

**When Alert:**

**Breakout Mode:**
```
Action: Watch chart for pullback to midpoint
Then: Enter when price hits midpoint
```

**Retest Mode:**
```
Action: Enter immediately at market
```

### Execution Tips

1. Use limit orders at midpoint
2. Set stops immediately after entry
3. Don't chase - wait for proper retest
4. Risk 1-2% per trade
5. Account for $0.10-0.20 slippage

---

## 🧪 Backtesting

### Quick Backtest

```bash
py orb_backtest.py
```

Tests last 7 days automatically.

### Example Output

```
BACKTEST RESULTS
Total Trades:  4
Winning:       3 (75.0%)
Total P&L:     $2.50
Avg R:R:       1.92:1
Profit Factor: 6.00
```

### Customize

Edit `orb_backtest.py`:
```python
SYMBOL = 'QQQ'
BREAKOUT_DISTANCE = 1.5
RISK_REWARD_RATIO = 2.5
```

### Diagnostic Tools

**See daily breakdown:**
```bash
py orb_trace.py
```

**Compare symbols:**
```bash
py orb_diagnostic.py
```

---

## 🔔 Notifications Setup

### Telegram (Recommended!)

**Setup (2 minutes):**

1. Message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow instructions
3. Copy bot token
4. Message [@userinfobot](https://t.me/userinfobot)
5. Copy chat ID

**Add to scanner:**
```python
TELEGRAM_BOT_TOKEN = "123456789:ABCdef..."
TELEGRAM_CHAT_ID = "123456789"
```

**Test:**
```bash
py orb_breakout_alerts.py
```

You'll see:
```
Testing Telegram connection...
✅ Telegram notifications enabled and working!
```

And receive: "🟢 ORB Scanner Online"

### Email (Gmail)

1. Enable 2FA on Google Account
2. Create App Password: https://myaccount.google.com/apppasswords
3. Add to scanner:
```python
SMTP_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'your@gmail.com',
    'sender_password': 'app_password',
    'recipient_email': 'recipient@email.com'
}
```

---

## 📁 Files Guide

### Core Scanners

| File | Purpose |
|------|---------|
| `orb_breakout_alerts.py` | Alert on breakout (NEW!) |
| `orb_scanner_notifications.py` | Alert on retest |
| `orb_scanner.py` | Console only |
| `orb_web_dashboard.py` | Visual dashboard |

### Analysis Tools

| File | Purpose |
|------|---------|
| `orb_backtest.py` | Test strategy |
| `orb_trace.py` | Daily analysis |
| `orb_diagnostic.py` | Compare symbols |
| `test_backtest.py` | Quick validation |

### Documentation

| File | Content |
|------|---------|
| `README.md` | Complete guide (this file) |
| `QUICKSTART.md` | 5-minute setup |
| `TRADING_GUIDE.md` | Live trading |
| `BREAKOUT_MODE_GUIDE.md` | Breakout mode |
| `BACKTEST_GUIDE.md` | Backtesting |

---

## 🎛️ Configuration

### Basic Settings

```python
SYMBOLS = ['SPY', 'QQQ', ...]
BREAKOUT_DISTANCE = 2.0
CHECK_INTERVAL = 60
RISK_REWARD_RATIO = 2.0
```

### Time Settings

```python
OR_START = time(9, 30)
OR_END = time(9, 45)
SESSION_END = time(16, 0)
TIMEZONE = "America/New_York"
```

### Presets

**Conservative:**
```python
BREAKOUT_DISTANCE = 3.0
RISK_REWARD_RATIO = 2.5
```

**Aggressive:**
```python
BREAKOUT_DISTANCE = 1.0
RISK_REWARD_RATIO = 1.5
```

---

## 🐛 Troubleshooting

### No Data Retrieved

**Solutions:**
- Check internet connection
- Verify market hours (9:30 AM - 4:00 PM ET)
- Use recent dates (last 7 days)
- Try different symbol

### No Signals

**Reasons:**
- Before 9:45 AM (OR not captured)
- No breakouts occurred
- No retests (strong trends)
- After hours

**Check:**
```bash
py orb_trace.py  # See what happened
```

**Expected:**
- Quiet weeks: 0-2 signals
- Normal weeks: 3-7 signals
- Volatile weeks: 8-15 signals

### Telegram Issues

**Checklist:**
- ✅ Bot token correct?
- ✅ Chat ID correct (numeric)?
- ✅ Messaged bot once?

**Test:**
```bash
py orb_breakout_alerts.py
# Should show: ✅ Telegram notifications enabled!
```

### Web Dashboard

**Unicode error:** Fixed in latest version

**Port in use:**
```python
# Change port in code:
socketio.run(app, port=5001)
```

---

## ❓ FAQ

**Q: How many signals per week?**  
A: 0-15 depending on volatility

**Q: Which mode is better?**  
A: Breakout mode for active traders, Retest for busy traders

**Q: Can I trade crypto?**  
A: Yes, adjust times for 24/7 markets

**Q: Why 2:1 R:R?**  
A: Professional standard - profitable with >50% win rate

**Q: Can it auto-trade?**  
A: Not currently - alerts only (can integrate broker API)

**Q: Works on VPS?**  
A: Yes! Perfect for 24/7 monitoring

**Q: Multiple timeframes?**  
A: Can modify for 5min/15min/30min OR

---

## 📈 Performance Tips

### Optimize Signals

1. Test different breakout distances
2. Focus on liquid symbols (SPY, QQQ)
3. Best times: First and last hour
4. Volatile periods: Earnings, FOMC

### Improve Win Rate

1. Use confluence (multiple symbols)
2. Avoid very narrow/wide ORs
3. Morning signals often better
4. Skip late-day signals

### System Performance

1. Reduce check interval: `CHECK_INTERVAL = 30`
2. Limit symbols for speed
3. Use VPS for 24/7 uptime

---

## 🎓 Resources

### ORB Strategy
- "Opening Range Breakout" by Toby Crabel
- YouTube: "ORB Strategy Explained"
- TradingView: #ORB tag

### Python Trading
- Python for Finance (Udemy)
- yfinance documentation
- TA-Lib for indicators

### Risk Management
- "Trade Your Way to Financial Freedom"
- Position sizing calculators
- Kelly Criterion

---

## 🔄 Updates

### v2.0 (December 2024)
✅ Added Breakout Alert Mode  
✅ Fixed Telegram test messages  
✅ Fixed web dashboard Unicode  
✅ Enhanced backtesting  
✅ Added diagnostic tools  

### Roadmap
🔜 Discord notifications  
🔜 Multiple timeframe ORs  
🔜 Broker API integration  
🔜 Mobile app  
🔜 ML signal filtering  

---

## 🚀 Ready to Start?

**Tomorrow morning before 9:30 AM:**

```bash
# Choose your mode:
py orb_breakout_alerts.py
# OR
py orb_scanner_notifications.py
# OR
py orb_web_dashboard.py
```

---

## 📜 License & Disclaimer

Use however you like! 

**Disclaimer:** Trading involves risk. This is a tool, not financial advice. Test with paper trading first. Past performance ≠ future results.

---

## 🙏 Final Notes

### Before Going Live

1. ✅ Run backtests
2. ✅ Paper trade 1-2 weeks
3. ✅ Test notifications
4. ✅ Understand strategy
5. ✅ Set position sizing
6. ✅ Have risk plan

### Success Tips

- **Be Patient** - Not every day has signals
- **Be Disciplined** - Follow the system
- **Be Consistent** - Same approach each time
- **Keep Records** - Track all trades
- **Review Weekly** - Learn and adjust

---

**Tutto pronto! Happy Trading! 📈🎯**

Version 2.0 | December 2024 | Python 3.8+  
*Built with ❤️ for professional ORB trading*