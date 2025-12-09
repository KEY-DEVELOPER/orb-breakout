"""
ORB Breakout Alert Scanner
Alerts you IMMEDIATELY when breakout occurs (before retest)
Then you can manually watch for retest opportunity
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
from typing import Dict, List, Tuple, Optional
import time as time_module
from dataclasses import dataclass
import logging
import asyncio
import aiohttp

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ORBBreakout:
    """Store breakout alert information"""
    symbol: str
    breakout_type: str  # 'LONG' or 'SHORT'
    timestamp: datetime
    breakout_price: float
    or_high: float
    or_low: float
    or_mid: float
    entry_level: float  # Where to enter on retest
    stop_loss: float
    target: float


class TelegramNotifier:
    """Send notifications via Telegram"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def send_message(self, message: str):
        """Send message to Telegram"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sendMessage"
                payload = {
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        return True
                    else:
                        print(f"Telegram error: {response.status}")
                        return False
        except Exception as e:
            print(f"Error sending Telegram message: {e}")
            return False
    
    async def send_test_message(self):
        """Send test message to verify connection"""
        message = "🟢 <b>ORB Scanner Online</b>\n\nBot is running and ready to send breakout alerts!"
        return await self.send_message(message)
    
    def format_breakout_message(self, breakout: ORBBreakout) -> str:
        """Format breakout alert for Telegram"""
        emoji = "🔼" if breakout.breakout_type == "LONG" else "🔽"
        
        message = f"""
{emoji} <b>BREAKOUT ALERT - {breakout.symbol}</b> {emoji}

<b>Type:</b> {breakout.breakout_type}
<b>Time:</b> {breakout.timestamp.strftime('%H:%M:%S')}
<b>Breakout Price:</b> ${breakout.breakout_price:.2f}

<b>Opening Range:</b>
• High: ${breakout.or_high:.2f}
• Mid: ${breakout.or_mid:.2f}
• Low: ${breakout.or_low:.2f}

<b>WATCH FOR RETEST</b>
Entry Level: ${breakout.entry_level:.2f} (midpoint)
Stop Loss: ${breakout.stop_loss:.2f}
Target: ${breakout.target:.2f} (2:1 R:R)

⏰ Monitor for pullback to midpoint!
"""
        return message.strip()


class ORBBreakoutScanner:
    """
    ORB Scanner with Breakout Alerts (Immediate)
    Alerts you when breakout occurs, you watch for retest
    """
    
    def __init__(
        self,
        symbols: List[str],
        breakout_distance: float = 2.0,
        timezone: str = "America/New_York",
        or_start: time = time(9, 30),
        or_end: time = time(9, 45),
        session_end: time = time(16, 0),
        check_interval: int = 60,
        telegram_notifier: Optional[TelegramNotifier] = None
    ):
        self.symbols = symbols
        self.breakout_distance = breakout_distance
        self.timezone = pytz.timezone(timezone)
        self.or_start = or_start
        self.or_end = or_end
        self.session_end = session_end
        self.check_interval = check_interval
        self.telegram_notifier = telegram_notifier
        
        # Track state
        self.or_data: Dict[str, Dict] = {}
        self.breakout_state: Dict[str, Dict] = {}
        self.breakouts_today: Dict[str, List[ORBBreakout]] = {}
        
        self._initialize_states()
    
    def _initialize_states(self):
        """Initialize tracking states"""
        for symbol in self.symbols:
            self.or_data[symbol] = {
                'high': None,
                'low': None,
                'mid': None,
                'captured': False
            }
            self.breakout_state[symbol] = {
                'long_alerted': False,  # Only alert once per direction
                'short_alerted': False,
                'last_check': None
            }
            self.breakouts_today[symbol] = []
    
    def is_new_day(self, symbol: str) -> bool:
        """Check if new trading day"""
        last_check = self.breakout_state[symbol]['last_check']
        if last_check is None:
            return True
        
        now = datetime.now(self.timezone)
        return now.date() > last_check.date()
    
    def reset_for_new_day(self, symbol: str):
        """Reset for new day"""
        self.or_data[symbol] = {
            'high': None,
            'low': None,
            'mid': None,
            'captured': False
        }
        self.breakout_state[symbol] = {
            'long_alerted': False,
            'short_alerted': False,
            'last_check': datetime.now(self.timezone)
        }
        self.breakouts_today[symbol] = []
        logger.info(f"Reset state for {symbol} - New trading day")
    
    def get_current_data(self, symbol: str, period: str = '1d', interval: str = '1m') -> pd.DataFrame:
        """Fetch current intraday data"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                return pd.DataFrame()
            
            df.index = df.index.tz_convert(self.timezone)
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()
    
    def capture_opening_range(self, symbol: str, df: pd.DataFrame) -> bool:
        """Capture OR if not done yet"""
        if self.or_data[symbol]['captured']:
            return True
        
        or_bars = df.between_time(
            self.or_start.strftime('%H:%M:%S'),
            self.or_end.strftime('%H:%M:%S')
        )
        
        if len(or_bars) == 0:
            return False
        
        or_high = or_bars['High'].max()
        or_low = or_bars['Low'].min()
        or_mid = (or_high + or_low) / 2
        
        self.or_data[symbol]['high'] = or_high
        self.or_data[symbol]['low'] = or_low
        self.or_data[symbol]['mid'] = or_mid
        self.or_data[symbol]['captured'] = True
        
        logger.info(f"{symbol} OR Captured - High: {or_high:.2f}, Low: {or_low:.2f}, Mid: {or_mid:.2f}")
        return True
    
    def check_for_breakouts(self, symbol: str, df: pd.DataFrame) -> Optional[ORBBreakout]:
        """
        Check for breakouts and alert IMMEDIATELY
        Returns ORBBreakout if new breakout detected
        """
        if not self.or_data[symbol]['captured']:
            return None
        
        or_high = self.or_data[symbol]['high']
        or_low = self.or_data[symbol]['low']
        or_mid = self.or_data[symbol]['mid']
        
        if len(df) < 2:
            return None
        
        current_bar = df.iloc[-1]
        current_close = current_bar['Close']
        
        state = self.breakout_state[symbol]
        
        # LONG BREAKOUT
        if not state['long_alerted']:
            if current_close >= or_high + self.breakout_distance:
                # Calculate trade levels
                entry = or_mid
                stop = or_low
                risk = entry - stop
                target = entry + (risk * 2.0)  # 2:1 R:R
                
                breakout = ORBBreakout(
                    symbol=symbol,
                    breakout_type='LONG',
                    timestamp=current_bar.name,
                    breakout_price=current_close,
                    or_high=or_high,
                    or_low=or_low,
                    or_mid=or_mid,
                    entry_level=entry,
                    stop_loss=stop,
                    target=target
                )
                
                state['long_alerted'] = True
                self.breakouts_today[symbol].append(breakout)
                logger.info(f"{symbol} - LONG breakout detected at {current_close:.2f}")
                return breakout
        
        # SHORT BREAKOUT
        if not state['short_alerted']:
            if current_close <= or_low - self.breakout_distance:
                # Calculate trade levels
                entry = or_mid
                stop = or_high
                risk = stop - entry
                target = entry - (risk * 2.0)  # 2:1 R:R
                
                breakout = ORBBreakout(
                    symbol=symbol,
                    breakout_type='SHORT',
                    timestamp=current_bar.name,
                    breakout_price=current_close,
                    or_high=or_high,
                    or_low=or_low,
                    or_mid=or_mid,
                    entry_level=entry,
                    stop_loss=stop,
                    target=target
                )
                
                state['short_alerted'] = True
                self.breakouts_today[symbol].append(breakout)
                logger.info(f"{symbol} - SHORT breakout detected at {current_close:.2f}")
                return breakout
        
        return None
    
    def is_trading_hours(self) -> bool:
        """Check if in trading hours"""
        now = datetime.now(self.timezone)
        current_time = now.time()
        return self.or_end <= current_time < self.session_end
    
    def print_breakout(self, breakout: ORBBreakout):
        """Print breakout alert"""
        print("\n" + "="*70)
        print(f"{'🔼 LONG' if breakout.breakout_type == 'LONG' else '🔽 SHORT'} BREAKOUT: {breakout.symbol}")
        print("="*70)
        print(f"Time:           {breakout.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Breakout Price: ${breakout.breakout_price:.2f}")
        print(f"")
        print(f"Opening Range:")
        print(f"  High: ${breakout.or_high:.2f}")
        print(f"  Mid:  ${breakout.or_mid:.2f}")
        print(f"  Low:  ${breakout.or_low:.2f}")
        print(f"")
        print(f"⏰ WATCH FOR RETEST OF MIDPOINT")
        print(f"Entry:  ${breakout.entry_level:.2f} (when price pulls back to mid)")
        print(f"Stop:   ${breakout.stop_loss:.2f}")
        print(f"Target: ${breakout.target:.2f} (2:1 R:R)")
        print("="*70 + "\n")
    
    def scan_all_symbols(self) -> List[ORBBreakout]:
        """Scan all symbols for breakouts"""
        new_breakouts = []
        
        if not self.is_trading_hours():
            return new_breakouts
        
        for symbol in self.symbols:
            try:
                if self.is_new_day(symbol):
                    self.reset_for_new_day(symbol)
                
                df = self.get_current_data(symbol, period='1d', interval='1m')
                
                if df.empty:
                    continue
                
                if not self.or_data[symbol]['captured']:
                    self.capture_opening_range(symbol, df)
                
                breakout = self.check_for_breakouts(symbol, df)
                
                if breakout:
                    new_breakouts.append(breakout)
                    self.print_breakout(breakout)
                
                self.breakout_state[symbol]['last_check'] = datetime.now(self.timezone)
                
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
        
        return new_breakouts
    
    async def send_notifications(self, breakout: ORBBreakout):
        """Send notifications for breakout"""
        if self.telegram_notifier:
            message = self.telegram_notifier.format_breakout_message(breakout)
            await self.telegram_notifier.send_message(message)
    
    def get_status_summary(self) -> str:
        """Get current status"""
        lines = ["\n" + "="*80]
        lines.append(f"ORB Breakout Scanner - {datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("="*80)
        
        for symbol in self.symbols:
            or_info = self.or_data[symbol]
            state = self.breakout_state[symbol]
            
            status_line = f"{symbol:8s} | "
            
            if not or_info['captured']:
                status_line += "⏳ Waiting for OR"
            else:
                status_line += f"OR: {or_info['low']:.2f}-{or_info['high']:.2f} (Mid: {or_info['mid']:.2f}) | "
                
                if state['long_alerted']:
                    status_line += "🔼 LONG breakout alerted"
                elif state['short_alerted']:
                    status_line += "🔽 SHORT breakout alerted"
                else:
                    status_line += "👀 Watching for breakout"
                
                breakouts_count = len(self.breakouts_today[symbol])
                if breakouts_count > 0:
                    status_line += f" | {breakouts_count} alert(s) today"
            
            lines.append(status_line)
        
        lines.append("="*80)
        return "\n".join(lines)
    
    def run(self, duration_minutes: Optional[int] = None):
        """Run the scanner"""
        logger.info("Starting ORB Breakout Scanner...")
        logger.info(f"Monitoring {len(self.symbols)} symbols")
        logger.info(f"Check interval: {self.check_interval} seconds")
        logger.info("MODE: Breakout Alert (alerts on breakout, you watch for retest)")
        
        start_time = datetime.now()
        
        try:
            iteration = 0
            
            while True:
                if duration_minutes:
                    elapsed = (datetime.now() - start_time).total_seconds() / 60
                    if elapsed >= duration_minutes:
                        break
                
                breakouts = self.scan_all_symbols()
                
                # Send notifications
                if breakouts and self.telegram_notifier:
                    for breakout in breakouts:
                        asyncio.run(self.send_notifications(breakout))
                
                # Print status every 10 iterations
                iteration += 1
                if iteration % 10 == 0:
                    print(self.get_status_summary())
                
                time_module.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("\nScanner stopped by user")
            print(self.get_status_summary())


def main():
    """Main function"""
    
    # Watchlist
    SYMBOLS = [
        'SPY', 'QQQ', 'DIA', 'IWM',
        'AAPL', 'MSFT', 'TSLA', 'NVDA', 'GOOGL', 'AMZN',
        'GLD', 'SLV', 'USO', 'UNG', 'VXX'
    ]
    
    # TELEGRAM SETUP (optional but recommended!)
    TELEGRAM_BOT_TOKEN = ""  # "YOUR_BOT_TOKEN"
    TELEGRAM_CHAT_ID = 11111    # "YOUR_CHAT_ID"
    
    # Setup Telegram
    telegram_notifier = None
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        telegram_notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        
        # Send test message
        print("Testing Telegram connection...")
        result = asyncio.run(telegram_notifier.send_test_message())
        if result:
            print("✅ Telegram notifications enabled and working!")
        else:
            print("⚠️ Telegram test message failed - check your credentials")
    
    # Create scanner
    scanner = ORBBreakoutScanner(
        symbols=SYMBOLS,
        breakout_distance=2.0,
        timezone="America/New_York",
        check_interval=60,
        telegram_notifier=telegram_notifier
    )
    
    # Run
    print("\n🚀 ORB Breakout Alert Scanner started!")
    print(f"📊 Monitoring {len(SYMBOLS)} symbols")
    print("⏰ Checking every 60 seconds")
    print("")
    print("🔔 MODE: Breakout Alert")
    print("   You'll be alerted WHEN breakout occurs")
    print("   Then watch for retest of midpoint manually")
    print("")
    
    if TELEGRAM_BOT_TOKEN:
        print("📱 Telegram notifications: ENABLED")
    else:
        print("📱 Telegram notifications: DISABLED (set token to enable)")
    
    print("\nPress Ctrl+C to stop\n")
    
    scanner.run()


if __name__ == "__main__":
    main()