#!/usr/bin/env python3
"""
ORB Scanner Launcher
Simple menu to start the scanner in different modes
"""

import sys
import os

def print_banner():
    """Print ASCII banner"""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     🎯  ORB BREAKOUT SCANNER BOT  🎯                      ║
║                                                           ║
║     Multi-Asset Opening Range Breakout Monitor           ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"""
    print(banner)

def print_menu():
    """Print main menu"""
    menu = """
Choose your scanning mode:

1️⃣  Basic Scanner (Console)
   → Prints signals to terminal
   → Simple and straightforward
   → Good for testing

2️⃣  Scanner with Notifications
   → Telegram alerts 📱
   → Email alerts 📧
   → Console output
   → Best for active trading

3️⃣  Web Dashboard
   → Beautiful browser interface 🌐
   → Real-time updates
   → Signal history
   → Best for monitoring multiple assets

4️⃣  Configuration Help
   → Setup Telegram
   → Setup Email
   → Customize watchlist

5️⃣  Exit

"""
    print(menu)

def show_config_help():
    """Show configuration help"""
    help_text = """
╔═══════════════════════════════════════════════════════════╗
║                  CONFIGURATION HELP                       ║
╚═══════════════════════════════════════════════════════════╝

📱 TELEGRAM SETUP
-----------------
1. Open Telegram and message @BotFather
2. Send: /newbot
3. Follow instructions to create bot
4. Copy your bot token (format: 123456789:ABCdef...)
5. Message @userinfobot to get your chat ID
6. Edit orb_scanner_notifications.py:
   TELEGRAM_BOT_TOKEN = "your_token_here"
   TELEGRAM_CHAT_ID = "your_chat_id"

📧 EMAIL SETUP (Gmail)
---------------------
1. Enable 2-Factor Authentication on Google Account
2. Go to: https://myaccount.google.com/apppasswords
3. Create new app password
4. Edit orb_scanner_notifications.py:
   SMTP_CONFIG = {
       'smtp_server': 'smtp.gmail.com',
       'smtp_port': 587,
       'sender_email': 'your@gmail.com',
       'sender_password': 'your_app_password',
       'recipient_email': 'recipient@email.com'
   }

📊 CUSTOMIZE WATCHLIST
----------------------
Edit the SYMBOLS list in any scanner file:

SYMBOLS = [
    'SPY',    # S&P 500
    'QQQ',    # Nasdaq
    'AAPL',   # Apple
    'TSLA',   # Tesla
    # Add your symbols here!
]

⚙️ ADJUST PARAMETERS
--------------------
In scanner initialization:

scanner = ORBScanner(
    symbols=SYMBOLS,
    breakout_distance=2.0,    # Points for breakout
    timezone="America/New_York",
    check_interval=60,        # Seconds between checks
)

Press Enter to return to menu...
"""
    print(help_text)
    input()

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import yfinance
        import pandas
        import pytz
        return True
    except ImportError as e:
        print(f"\n❌ Missing dependency: {e}")
        print("\n💡 Install dependencies with:")
        print("   pip install -r requirements.txt\n")
        return False

def run_basic_scanner():
    """Run basic console scanner"""
    print("\n🚀 Starting Basic Scanner...")
    print("=" * 60)
    print("Press Ctrl+C to stop")
    print("=" * 60 + "\n")
    
    try:
        import orb_scanner
        orb_scanner.main()
    except KeyboardInterrupt:
        print("\n\n✅ Scanner stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")

def run_notification_scanner():
    """Run scanner with notifications"""
    print("\n🚀 Starting Scanner with Notifications...")
    print("=" * 60)
    print("Configure Telegram/Email in orb_scanner_notifications.py")
    print("Press Ctrl+C to stop")
    print("=" * 60 + "\n")
    
    try:
        import orb_scanner_notifications
        orb_scanner_notifications.main()
    except KeyboardInterrupt:
        print("\n\n✅ Scanner stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")

def run_web_dashboard():
    """Run web dashboard"""
    print("\n🚀 Starting Web Dashboard...")
    print("=" * 60)
    print("Open your browser to: http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("=" * 60 + "\n")
    
    try:
        import orb_web_dashboard
        orb_web_dashboard.main()
    except KeyboardInterrupt:
        print("\n\n✅ Dashboard stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")

def main():
    """Main launcher"""
    if not check_dependencies():
        return
    
    while True:
        print_banner()
        print_menu()
        
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == '1':
            run_basic_scanner()
        elif choice == '2':
            run_notification_scanner()
        elif choice == '3':
            run_web_dashboard()
        elif choice == '4':
            show_config_help()
        elif choice == '5':
            print("\n👋 Goodbye! Happy trading!")
            break
        else:
            print("\n❌ Invalid choice. Please try again.")
            input("Press Enter to continue...")
        
        # Clear screen (optional)
        os.system('clear' if os.name == 'posix' else 'cls')

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
