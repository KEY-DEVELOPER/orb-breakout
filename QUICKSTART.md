# 🚀 QUICK START GUIDE

## Installation (5 minutes)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Choose Your Mode

#### Option A: Simple Console Scanner
```bash
python orb_scanner.py
```
**Best for:** Testing the strategy, simple monitoring

#### Option B: Menu Launcher
```bash
python launch_scanner.py
```
**Best for:** Easy navigation between different modes

#### Option C: Web Dashboard
```bash
python orb_web_dashboard.py
```
Then open: http://localhost:5000
**Best for:** Visual monitoring, multiple assets

## 📊 What You'll See

### Console Output Example:
```
============================================================
🚨 LONG SIGNAL: SPY
============================================================
Time:          2024-12-09 10:23:15
Current Price: $595.50
OR High:       $595.00
OR Mid (Entry): $594.50
OR Low:        $594.00
Range:         $1.00
============================================================
```

### Status Updates Every 10 Minutes:
```
================================================================================
ORB Scanner Status - 2024-12-09 10:30:00
================================================================================
SPY      | OR: 594.00-595.00 (Mid: 594.50) | 👀 Watching for breakout
QQQ      | OR: 512.00-513.50 (Mid: 512.75) | ✅ LONG Active (watching for retest)
AAPL     | OR: 194.50-195.20 (Mid: 194.85) | 👀 Watching for breakout | Signals today: 1
================================================================================
```

## ⚙️ Quick Customization

### Change Symbols (Edit any .py file)
```python
SYMBOLS = [
    'SPY',    # S&P 500
    'QQQ',    # Nasdaq
    'AAPL',   # Your favorite stock
    'TSLA',   # Add any ticker!
]
```

### Adjust Breakout Distance
```python
scanner = ORBScanner(
    symbols=SYMBOLS,
    breakout_distance=2.0,  # Change this number
    check_interval=60,      # Seconds between checks
)
```

## 🔔 Enable Notifications (Optional)

### Telegram (Easiest)
1. Message [@BotFather](https://t.me/BotFather)
2. Create bot → get token
3. Message [@userinfobot](https://t.me/userinfobot) → get chat_id
4. Edit `orb_scanner_notifications.py`:
```python
TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"
```
5. Run: `python orb_scanner_notifications.py`

### Email (Gmail)
1. Enable 2FA on Google Account
2. Create App Password: https://myaccount.google.com/apppasswords
3. Edit `orb_scanner_notifications.py`:
```python
SMTP_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'your@gmail.com',
    'sender_password': 'app_password_here',
    'recipient_email': 'recipient@email.com'
}
```

## 🧪 Test the Strategy (Backtest)

```bash
python orb_backtest.py
```

Edit the file to test different symbols and date ranges:
```python
SYMBOL = 'SPY'
START_DATE = '2024-11-01'
END_DATE = '2024-12-01'
PROFIT_TARGET = 3.0  # Adjust this
STOP_LOSS = 2.0      # And this
```

## 📱 Run 24/7 on Server

### Using screen (Linux/Mac)
```bash
screen -S orb-bot
python orb_scanner_notifications.py
# Press Ctrl+A, then D to detach
# Reconnect with: screen -r orb-bot
```

### Using nohup
```bash
nohup python orb_scanner_notifications.py > scanner.log 2>&1 &
```

## 🐛 Troubleshooting

**No signals appearing?**
- Check if market is open (9:30 AM - 4:00 PM ET)
- Wait until after 9:45 AM for OR to be captured
- Try with SPY or QQQ first (high liquidity)

**"No data retrieved" error?**
- Symbol might be incorrect
- Market might be closed
- Check your internet connection

**Telegram not working?**
- Verify bot token is correct (from BotFather)
- Make sure you messaged the bot at least once
- Chat ID should be numeric, not username

**Email not sending?**
- Must use App Password, not regular Gmail password
- 2FA must be enabled on Google Account
- Check SMTP settings are correct

## 💡 Pro Tips

1. **Start Small**: Test with 3-5 symbols first
2. **Monitor SPY**: Always include SPY as benchmark
3. **Check Regularly**: First week, monitor frequently to ensure it's working
4. **Backtest First**: Run backtest to understand win rate before live trading
5. **Set Alerts**: Enable Telegram for instant notifications

## 📚 Next Steps

1. ✅ Run basic scanner to see it work
2. ✅ Customize your watchlist
3. ✅ Run backtest on your symbols
4. ✅ Setup notifications
5. ✅ Paper trade the signals for a week
6. ✅ Optimize parameters based on results

## 🎯 Strategy Reminder

**Signal Generation:**
1. Opening Range captured at 9:30-9:45 AM
2. Wait for breakout (close beyond OR high/low + distance)
3. Signal fires when price retests OR midpoint
4. Long signal = buy at midpoint after upward breakout
5. Short signal = sell at midpoint after downward breakout

**Entry:** OR midpoint
**Stop Loss:** Your choice (backtest suggests ~2 points)
**Target:** Your choice (backtest suggests ~3 points)

---

**Need Help?** Check the full README.md for detailed documentation!

Happy Trading! 📈🎯
