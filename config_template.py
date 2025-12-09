"""
ORB Scanner Configuration Template
Copy this file to config.py and customize your settings
"""

# ============================================
# WATCHLIST CONFIGURATION
# ============================================

# Add all symbols you want to monitor
SYMBOLS = [
    # Major US Indices
    'SPY',      # S&P 500 ETF
    'QQQ',      # Nasdaq 100 ETF
    'DIA',      # Dow Jones ETF
    'IWM',      # Russell 2000 ETF
    
    # Large Cap Tech
    'AAPL',     # Apple
    'MSFT',     # Microsoft
    'GOOGL',    # Google
    'AMZN',     # Amazon
    'META',     # Meta/Facebook
    'TSLA',     # Tesla
    'NVDA',     # Nvidia
    'AMD',      # AMD
    
    # Finance
    'JPM',      # JP Morgan
    'BAC',      # Bank of America
    'GS',       # Goldman Sachs
    'V',        # Visa
    
    # Healthcare
    'JNJ',      # Johnson & Johnson
    'UNH',      # UnitedHealth
    
    # Energy
    'XOM',      # Exxon Mobil
    'CVX',      # Chevron
    
    # Metals & Commodities
    'GLD',      # Gold ETF
    'SLV',      # Silver ETF
    'USO',      # Oil ETF
    'UNG',      # Natural Gas ETF
    
    # International
    'EWJ',      # Japan ETF
    'EWZ',      # Brazil ETF
    'FXI',      # China ETF
    
    # Crypto (via ETFs/Stocks)
    'BITO',     # Bitcoin Futures ETF
    'COIN',     # Coinbase
    'MSTR',     # MicroStrategy
    
    # Volatility
    'VXX',      # VIX Short-Term Futures ETF
    'UVXY',     # 2x VIX ETF
    
    # Add your custom symbols below:
    # 'YOUR_SYMBOL',
]

# ============================================
# STRATEGY PARAMETERS
# ============================================

# Distance (in points) beyond OR high/low to trigger breakout
BREAKOUT_DISTANCE = 2.0

# Check interval in seconds (60 = check every minute)
CHECK_INTERVAL = 60

# ============================================
# TIMEZONE CONFIGURATION
# ============================================

# Choose your trading timezone
# Options: "America/New_York", "America/Chicago", "Europe/London", 
#          "Asia/Tokyo", "Asia/Hong_Kong"
TIMEZONE = "America/New_York"

# ============================================
# OPENING RANGE TIMES
# ============================================

# OR period start time (24-hour format)
OR_START_HOUR = 9
OR_START_MINUTE = 30

# OR period end time (24-hour format)
OR_END_HOUR = 9
OR_END_MINUTE = 45

# Stop monitoring at this time (24-hour format)
SESSION_END_HOUR = 16
SESSION_END_MINUTE = 0

# ============================================
# TELEGRAM NOTIFICATIONS (Optional)
# ============================================

# Enable Telegram notifications
TELEGRAM_ENABLED = False

# Get bot token from @BotFather on Telegram
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Get your chat_id from @userinfobot
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"

# ============================================
# EMAIL NOTIFICATIONS (Optional)
# ============================================

# Enable email notifications
EMAIL_ENABLED = False

# Gmail configuration (for other providers, adjust SMTP settings)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "your_email@gmail.com"
SENDER_PASSWORD = "your_app_password"  # Use App Password for Gmail
RECIPIENT_EMAIL = "recipient@email.com"

# ============================================
# BACKTESTING PARAMETERS
# ============================================

# Exit strategy for backtesting
PROFIT_TARGET = 3.0    # Points profit target (None = no target)
STOP_LOSS = 2.0        # Points stop loss (None = no stop)
TRAILING_STOP = None   # Points trailing stop (None = disabled)

# ============================================
# ADVANCED SETTINGS
# ============================================

# Enable debug logging
DEBUG_MODE = False

# Save signals to CSV file
SAVE_SIGNALS_TO_FILE = True
SIGNALS_FILE_PATH = "orb_signals.csv"

# Maximum number of symbols to scan simultaneously
# (lower this if you have API rate limits)
MAX_CONCURRENT_SYMBOLS = 50

# ============================================
# EXAMPLE PRESETS
# ============================================

# Uncomment one of these to use a preset configuration

# Preset 1: Conservative (lower risk)
# BREAKOUT_DISTANCE = 3.0
# PROFIT_TARGET = 2.0
# STOP_LOSS = 1.5

# Preset 2: Aggressive (higher risk/reward)
# BREAKOUT_DISTANCE = 1.5
# PROFIT_TARGET = 5.0
# STOP_LOSS = 2.5

# Preset 3: Day Trading (quick scalps)
# BREAKOUT_DISTANCE = 1.0
# PROFIT_TARGET = 1.5
# STOP_LOSS = 1.0
# CHECK_INTERVAL = 30  # Check every 30 seconds

# Preset 4: Swing Trading (larger moves)
# BREAKOUT_DISTANCE = 5.0
# PROFIT_TARGET = 10.0
# STOP_LOSS = 5.0
# SESSION_END_HOUR = 20  # Hold until after-hours
