"""
ORB Breakout Scanner Bot
Monitors multiple assets for Opening Range breakout and retest signals
Based on your TradingView indicator logic
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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ORBSignal:
    """Store ORB signal information"""
    symbol: str
    signal_type: str  # 'LONG' or 'SHORT'
    timestamp: datetime
    or_high: float
    or_low: float
    or_mid: float
    current_price: float


class ORBScanner:
    """
    Opening Range Breakout Scanner
    Monitors multiple assets and detects breakout + retest signals
    """
    
    def __init__(
        self,
        symbols: List[str],
        breakout_distance: float = 2.0,
        timezone: str = "America/New_York",
        or_start: time = time(9, 30),
        or_end: time = time(9, 45),
        session_end: time = time(16, 0),
        check_interval: int = 60  # seconds between checks
    ):
        self.symbols = symbols
        self.breakout_distance = breakout_distance
        self.timezone = pytz.timezone(timezone)
        self.or_start = or_start
        self.or_end = or_end
        self.session_end = session_end
        self.check_interval = check_interval
        
        # Track state for each symbol
        self.or_data: Dict[str, Dict] = {}
        self.breakout_state: Dict[str, Dict] = {}
        self.signals_today: Dict[str, List[ORBSignal]] = {}
        
        self._initialize_states()
    
    def _initialize_states(self):
        """Initialize tracking states for all symbols"""
        for symbol in self.symbols:
            self.or_data[symbol] = {
                'high': None,
                'low': None,
                'mid': None,
                'captured': False
            }
            self.breakout_state[symbol] = {
                'long_breakout_active': False,
                'short_breakout_active': False,
                'was_in_zone': True,
                'last_check': None
            }
            self.signals_today[symbol] = []
    
    def is_new_day(self, symbol: str) -> bool:
        """Check if it's a new trading day"""
        last_check = self.breakout_state[symbol]['last_check']
        if last_check is None:
            return True
        
        now = datetime.now(self.timezone)
        return now.date() > last_check.date()
    
    def reset_for_new_day(self, symbol: str):
        """Reset all tracking for a new day"""
        self.or_data[symbol] = {
            'high': None,
            'low': None,
            'mid': None,
            'captured': False
        }
        self.breakout_state[symbol] = {
            'long_breakout_active': False,
            'short_breakout_active': False,
            'was_in_zone': True,
            'last_check': datetime.now(self.timezone)
        }
        self.signals_today[symbol] = []
        logger.info(f"Reset state for {symbol} - New trading day")
    
    def get_current_data(self, symbol: str, period: str = '1d', interval: str = '1m') -> pd.DataFrame:
        """Fetch current intraday data for symbol"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                logger.warning(f"No data retrieved for {symbol}")
                return pd.DataFrame()
            
            # Convert to timezone
            df.index = df.index.tz_convert(self.timezone)
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()
    
    def capture_opening_range(self, symbol: str, df: pd.DataFrame) -> bool:
        """
        Capture the opening range high/low from 9:30-9:45
        Returns True if captured successfully
        """
        if self.or_data[symbol]['captured']:
            return True
        
        # Filter for OR period
        or_bars = df.between_time(
            self.or_start.strftime('%H:%M:%S'),
            self.or_end.strftime('%H:%M:%S')
        )
        
        if len(or_bars) == 0:
            return False
        
        # Capture the range
        or_high = or_bars['High'].max()
        or_low = or_bars['Low'].min()
        or_mid = (or_high + or_low) / 2
        
        self.or_data[symbol]['high'] = or_high
        self.or_data[symbol]['low'] = or_low
        self.or_data[symbol]['mid'] = or_mid
        self.or_data[symbol]['captured'] = True
        
        logger.info(f"{symbol} OR Captured - High: {or_high:.2f}, Low: {or_low:.2f}, Mid: {or_mid:.2f}")
        return True
    
    def check_breakout_and_retest(self, symbol: str, df: pd.DataFrame) -> Optional[ORBSignal]:
        """
        Check for breakout and retest signal
        Returns ORBSignal if signal detected, None otherwise
        """
        if not self.or_data[symbol]['captured']:
            return None
        
        or_high = self.or_data[symbol]['high']
        or_low = self.or_data[symbol]['low']
        or_mid = self.or_data[symbol]['mid']
        
        # Get current bar (last completed bar)
        if len(df) < 2:
            return None
        
        current_bar = df.iloc[-1]
        current_close = current_bar['Close']
        current_high = current_bar['High']
        current_low = current_bar['Low']
        
        state = self.breakout_state[symbol]
        
        # Check if price is inside the zone
        price_in_zone = current_close <= or_high and current_close >= or_low
        
        # Track when price returns to zone - this resets breakout eligibility
        if price_in_zone:
            if not state['was_in_zone']:
                logger.debug(f"{symbol} - Price back in zone")
            state['was_in_zone'] = True
            state['long_breakout_active'] = False
            state['short_breakout_active'] = False
        
        # LONG BREAKOUT: price closes beyond high + distance
        if state['was_in_zone'] and not state['long_breakout_active']:
            if current_close >= or_high + self.breakout_distance:
                state['long_breakout_active'] = True
                state['was_in_zone'] = False
                logger.info(f"{symbol} - LONG breakout detected at {current_close:.2f}")
        
        # SHORT BREAKOUT: price closes beyond low - distance
        if state['was_in_zone'] and not state['short_breakout_active']:
            if current_close <= or_low - self.breakout_distance:
                state['short_breakout_active'] = True
                state['was_in_zone'] = False
                logger.info(f"{symbol} - SHORT breakout detected at {current_close:.2f}")
        
        # LONG RETEST ENTRY
        if state['long_breakout_active']:
            if current_low <= or_mid:
                signal = ORBSignal(
                    symbol=symbol,
                    signal_type='LONG',
                    timestamp=current_bar.name,
                    or_high=or_high,
                    or_low=or_low,
                    or_mid=or_mid,
                    current_price=current_close
                )
                state['long_breakout_active'] = False
                self.signals_today[symbol].append(signal)
                return signal
        
        # SHORT RETEST ENTRY
        if state['short_breakout_active']:
            if current_high >= or_mid:
                signal = ORBSignal(
                    symbol=symbol,
                    signal_type='SHORT',
                    timestamp=current_bar.name,
                    or_high=or_high,
                    or_low=or_low,
                    or_mid=or_mid,
                    current_price=current_close
                )
                state['short_breakout_active'] = False
                self.signals_today[symbol].append(signal)
                return signal
        
        return None
    
    def is_trading_hours(self) -> bool:
        """Check if we're in trading hours"""
        now = datetime.now(self.timezone)
        current_time = now.time()
        
        # After OR ends and before session close
        return self.or_end <= current_time < self.session_end
    
    def scan_all_symbols(self) -> List[ORBSignal]:
        """
        Scan all symbols for signals
        Returns list of new signals detected
        """
        new_signals = []
        
        if not self.is_trading_hours():
            logger.debug("Outside trading hours")
            return new_signals
        
        for symbol in self.symbols:
            try:
                # Check for new day
                if self.is_new_day(symbol):
                    self.reset_for_new_day(symbol)
                
                # Get current data
                df = self.get_current_data(symbol, period='1d', interval='1m')
                
                if df.empty:
                    continue
                
                # Capture OR if not done yet
                if not self.or_data[symbol]['captured']:
                    self.capture_opening_range(symbol, df)
                
                # Check for signals
                signal = self.check_breakout_and_retest(symbol, df)
                
                if signal:
                    new_signals.append(signal)
                    self.print_signal(signal)
                
                # Update last check time
                self.breakout_state[symbol]['last_check'] = datetime.now(self.timezone)
                
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
        
        return new_signals
    
    def print_signal(self, signal: ORBSignal):
        """Print signal in a nice format"""
        print("\n" + "="*60)
        print(f"🚨 {signal.signal_type} SIGNAL: {signal.symbol}")
        print("="*60)
        print(f"Time:          {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Current Price: ${signal.current_price:.2f}")
        print(f"OR High:       ${signal.or_high:.2f}")
        print(f"OR Mid (Entry): ${signal.or_mid:.2f}")
        print(f"OR Low:        ${signal.or_low:.2f}")
        print(f"Range:         ${signal.or_high - signal.or_low:.2f}")
        print("="*60 + "\n")
    
    def get_status_summary(self) -> str:
        """Get current status of all symbols"""
        lines = ["\n" + "="*80]
        lines.append(f"ORB Scanner Status - {datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("="*80)
        
        for symbol in self.symbols:
            or_info = self.or_data[symbol]
            state = self.breakout_state[symbol]
            
            status_line = f"{symbol:8s} | "
            
            if not or_info['captured']:
                status_line += "⏳ Waiting for OR"
            else:
                status_line += f"OR: {or_info['low']:.2f}-{or_info['high']:.2f} (Mid: {or_info['mid']:.2f}) | "
                
                if state['long_breakout_active']:
                    status_line += "✅ LONG Active (watching for retest)"
                elif state['short_breakout_active']:
                    status_line += "✅ SHORT Active (watching for retest)"
                else:
                    status_line += "👀 Watching for breakout"
                
                # Add signals count
                signals_count = len(self.signals_today[symbol])
                if signals_count > 0:
                    status_line += f" | Signals today: {signals_count}"
            
            lines.append(status_line)
        
        lines.append("="*80)
        return "\n".join(lines)
    
    def run(self, duration_minutes: Optional[int] = None):
        """
        Run the scanner continuously
        duration_minutes: Run for specific duration (None = run indefinitely)
        """
        logger.info("Starting ORB Scanner...")
        logger.info(f"Monitoring {len(self.symbols)} symbols")
        logger.info(f"Check interval: {self.check_interval} seconds")
        
        start_time = datetime.now()
        
        try:
            while True:
                # Check if duration limit reached
                if duration_minutes:
                    elapsed = (datetime.now() - start_time).total_seconds() / 60
                    if elapsed >= duration_minutes:
                        logger.info(f"Duration limit reached ({duration_minutes} minutes)")
                        break
                
                # Scan all symbols
                signals = self.scan_all_symbols()
                
                # Print status every 10 checks (10 minutes if check_interval=60)
                if hasattr(self, '_scan_count'):
                    self._scan_count += 1
                else:
                    self._scan_count = 1
                
                if self._scan_count % 10 == 0:
                    print(self.get_status_summary())
                
                # Wait before next check
                time_module.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("\nScanner stopped by user")
            print(self.get_status_summary())


def main():
    """Example usage"""
    
    # Define symbols to monitor
    SYMBOLS = [
        # Major Indices
        'SPY',    # S&P 500
        'QQQ',    # Nasdaq
        'DIA',    # Dow Jones
        'IWM',    # Russell 2000
        
        # Popular Stocks
        'AAPL',   # Apple
        'MSFT',   # Microsoft
        'TSLA',   # Tesla
        'NVDA',   # Nvidia
        'GOOGL',  # Google
        'AMZN',   # Amazon
        
        # Metals
        'GLD',    # Gold
        'SLV',    # Silver
        
        # Futures ETFs
        'USO',    # Oil
        'UNG',    # Natural Gas
        
        # Volatility
        'VXX',    # VIX
    ]
    
    # Create scanner
    scanner = ORBScanner(
        symbols=SYMBOLS,
        breakout_distance=2.0,  # 2 points distance for breakout
        timezone="America/New_York",
        check_interval=60  # Check every 60 seconds
    )
    
    # Run scanner
    scanner.run()


if __name__ == "__main__":
    main()
