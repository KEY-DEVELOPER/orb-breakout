"""
ORB Backtester with Enhanced Data Fetcher
Uses StockDataFetcher for more reliable data retrieval
"""

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
import sys
import os

# Import the data fetcher
try:
    from data_fetcher import StockDataFetcher
except ImportError:
    print("Error: data_fetcher.py not found in current directory")
    print("Please ensure data_fetcher.py is in the same folder as this script")
    sys.exit(1)

@dataclass
class BacktestTrade:
    """Store trade information"""
    symbol: str
    date: str
    direction: str  # 'LONG' or 'SHORT'
    entry_time: str
    entry_price: float
    or_high: float
    or_mid: float
    or_low: float
    stop_loss: float = None
    profit_target: float = None
    exit_price: float = None
    exit_time: str = None
    pnl: float = None
    pnl_pct: float = None
    exit_reason: str = None


class ORBBacktesterEnhanced:
    """
    Enhanced ORB Backtester using reliable data fetcher
    """
    
    def __init__(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        breakout_distance: float = 2.0,
        timezone: str = "America/New_York",
        risk_reward_ratio: float = 2.0,
        use_or_range_stops: bool = True,
    ):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.breakout_distance = breakout_distance
        self.timezone = pytz.timezone(timezone)
        self.risk_reward_ratio = risk_reward_ratio
        self.use_or_range_stops = use_or_range_stops
        
        self.trades: List[BacktestTrade] = []
        self.df = None
        self.fetcher = StockDataFetcher(cache_dir="./backtest_data")
    
    def fetch_intraday_data(self) -> pd.DataFrame:
        """
        Fetch 1-minute intraday data
        Uses direct yfinance with better error handling
        """
        print(f"Fetching 1-minute data for {self.symbol}...")
        
        import yfinance as yf
        
        # Calculate date range
        start = pd.to_datetime(self.start_date)
        end = pd.to_datetime(self.end_date)
        
        # Fetch in 5-day chunks
        all_data = []
        current = start
        
        while current < end:
            chunk_end = min(current + timedelta(days=5), end)
            
            print(f"  Fetching {current.date()} to {chunk_end.date()}...")
            
            try:
                ticker = yf.Ticker(self.symbol)
                df_chunk = ticker.history(
                    start=current.strftime('%Y-%m-%d'),
                    end=chunk_end.strftime('%Y-%m-%d'),
                    interval='1m',
                    prepost=False
                )
                
                if not df_chunk.empty:
                    all_data.append(df_chunk)
                    print(f"    ✓ Retrieved {len(df_chunk)} bars")
                else:
                    print(f"    ⚠️ No data for this period")
                    
            except Exception as e:
                print(f"    ⚠️ Error: {e}")
            
            current = chunk_end
        
        if not all_data:
            raise ValueError(
                f"No data retrieved for {self.symbol}.\n"
                f"Note: Yahoo Finance typically provides 1-minute data for the last 7-30 days only.\n"
                f"Try using dates from the last 2 weeks."
            )
        
        # Combine all chunks
        df = pd.concat(all_data)
        
        # Convert timezone
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        df.index = df.index.tz_convert(self.timezone)
        
        print(f"✅ Total: {len(df)} bars retrieved")
        
        return df
    
    def get_daily_data(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Split data by trading day"""
        df = df.copy()
        df['date'] = df.index.date
        
        daily_data = {}
        for date, group in df.groupby('date'):
            # Only include days with sufficient data (at least 20 bars)
            if len(group) > 20:
                daily_data[str(date)] = group
        
        return daily_data
    
    def capture_opening_range(self, df: pd.DataFrame) -> Tuple[float, float, float]:
        """
        Capture OR high/low from 9:30-9:45
        Returns (or_high, or_low, or_mid)
        """
        try:
            or_bars = df.between_time('09:30:00', '09:45:00')
            
            if len(or_bars) == 0:
                return None, None, None
            
            or_high = or_bars['High'].max()
            or_low = or_bars['Low'].min()
            or_mid = (or_high + or_low) / 2
            
            return or_high, or_low, or_mid
        except:
            return None, None, None
    
    def simulate_day(self, date: str, df: pd.DataFrame) -> List[BacktestTrade]:
        """
        Simulate trading for one day with OR-based stops and 2:1 R:R
        """
        trades = []
        
        # Capture OR
        or_high, or_low, or_mid = self.capture_opening_range(df)
        
        if or_high is None:
            return trades
        
        or_range = or_high - or_low
        
        # Filter for trading hours (after 9:45)
        try:
            trading_bars = df[df.index.time >= time(9, 45)]
        except:
            return trades
        
        if len(trading_bars) == 0:
            return trades
        
        # State tracking
        long_breakout_active = False
        short_breakout_active = False
        was_in_zone = True
        in_trade = False
        current_trade = None
        
        for idx, bar in trading_bars.iterrows():
            close = bar['Close']
            high = bar['High']
            low = bar['Low']
            
            # Manage existing trade
            if in_trade and current_trade:
                
                if current_trade.direction == 'LONG':
                    # Check stop loss
                    if low <= current_trade.stop_loss:
                        current_trade.exit_price = current_trade.stop_loss
                        current_trade.exit_time = idx.strftime('%H:%M:%S')
                        current_trade.exit_reason = 'Stop Loss'
                        in_trade = False
                    # Check profit target
                    elif high >= current_trade.profit_target:
                        current_trade.exit_price = current_trade.profit_target
                        current_trade.exit_time = idx.strftime('%H:%M:%S')
                        current_trade.exit_reason = 'Profit Target (2:1)'
                        in_trade = False
                
                elif current_trade.direction == 'SHORT':
                    # Check stop loss
                    if high >= current_trade.stop_loss:
                        current_trade.exit_price = current_trade.stop_loss
                        current_trade.exit_time = idx.strftime('%H:%M:%S')
                        current_trade.exit_reason = 'Stop Loss'
                        in_trade = False
                    # Check profit target
                    elif low <= current_trade.profit_target:
                        current_trade.exit_price = current_trade.profit_target
                        current_trade.exit_time = idx.strftime('%H:%M:%S')
                        current_trade.exit_reason = 'Profit Target (2:1)'
                        in_trade = False
                
                # If trade closed, calculate PnL
                if not in_trade:
                    if current_trade.direction == 'LONG':
                        current_trade.pnl = current_trade.exit_price - current_trade.entry_price
                    else:
                        current_trade.pnl = current_trade.entry_price - current_trade.exit_price
                    
                    current_trade.pnl_pct = (current_trade.pnl / current_trade.entry_price) * 100
                    trades.append(current_trade)
                    current_trade = None
                    
                    # Reset for next trade
                    long_breakout_active = False
                    short_breakout_active = False
                    was_in_zone = True
            
            # Look for new signals
            if not in_trade:
                price_in_zone = close <= or_high and close >= or_low
                
                if price_in_zone:
                    was_in_zone = True
                    long_breakout_active = False
                    short_breakout_active = False
                
                # Check for breakouts
                if was_in_zone and not long_breakout_active:
                    if close >= or_high + self.breakout_distance:
                        long_breakout_active = True
                        was_in_zone = False
                
                if was_in_zone and not short_breakout_active:
                    if close <= or_low - self.breakout_distance:
                        short_breakout_active = True
                        was_in_zone = False
                
                # LONG entry on retest
                if long_breakout_active and low <= or_mid:
                    entry_price = or_mid
                    stop_loss = or_low if self.use_or_range_stops else entry_price - or_range
                    risk = entry_price - stop_loss
                    profit_target = entry_price + (risk * self.risk_reward_ratio)
                    
                    current_trade = BacktestTrade(
                        symbol=self.symbol,
                        date=date,
                        direction='LONG',
                        entry_time=idx.strftime('%H:%M:%S'),
                        entry_price=entry_price,
                        or_high=or_high,
                        or_mid=or_mid,
                        or_low=or_low,
                        stop_loss=stop_loss,
                        profit_target=profit_target
                    )
                    in_trade = True
                    long_breakout_active = False
                
                # SHORT entry on retest
                if short_breakout_active and high >= or_mid:
                    entry_price = or_mid
                    stop_loss = or_high if self.use_or_range_stops else entry_price + or_range
                    risk = stop_loss - entry_price
                    profit_target = entry_price - (risk * self.risk_reward_ratio)
                    
                    current_trade = BacktestTrade(
                        symbol=self.symbol,
                        date=date,
                        direction='SHORT',
                        entry_time=idx.strftime('%H:%M:%S'),
                        entry_price=entry_price,
                        or_high=or_high,
                        or_mid=or_mid,
                        or_low=or_low,
                        stop_loss=stop_loss,
                        profit_target=profit_target
                    )
                    in_trade = True
                    short_breakout_active = False
        
        # Close open trade at EOD
        if in_trade and current_trade:
            last_bar = trading_bars.iloc[-1]
            current_trade.exit_price = last_bar['Close']
            current_trade.exit_time = last_bar.name.strftime('%H:%M:%S')
            current_trade.exit_reason = 'EOD'
            
            if current_trade.direction == 'LONG':
                current_trade.pnl = current_trade.exit_price - current_trade.entry_price
            else:
                current_trade.pnl = current_trade.entry_price - current_trade.exit_price
            
            current_trade.pnl_pct = (current_trade.pnl / current_trade.entry_price) * 100
            trades.append(current_trade)
        
        return trades
    
    def run_backtest(self) -> Dict:
        """Run the backtest"""
        # Fetch data
        self.df = self.fetch_intraday_data()
        
        # Split by day
        daily_data = self.get_daily_data(self.df)
        
        print(f"\n📊 Backtesting {len(daily_data)} trading days...")
        print("=" * 60)
        
        # Simulate each day
        for date, df_day in daily_data.items():
            trades = self.simulate_day(date, df_day)
            self.trades.extend(trades)
            
            if trades:
                print(f"{date}: {len(trades)} trade(s)")
        
        print("=" * 60)
        
        # Calculate statistics
        from orb_backtest import ORBBacktester
        stats = ORBBacktester.calculate_statistics(self)
        
        return stats
    
    def print_results(self, stats: Dict):
        """Print results"""
        from orb_backtest import ORBBacktester
        # Use the print method from original
        temp = ORBBacktester(self.symbol, self.start_date, self.end_date)
        temp.trades = self.trades
        temp.print_results(stats)
    
    def export_trades(self, filename: str = None):
        """Export trades to CSV"""
        if not self.trades:
            print("No trades to export")
            return
        
        if filename is None:
            filename = f"orb_backtest_{self.symbol}_{self.start_date}_{self.end_date}.csv"
        
        df = pd.DataFrame([asdict(t) for t in self.trades])
        df.to_csv(filename, index=False)
        print(f"\n✅ Trades exported to: {filename}")


def main():
    """Run enhanced backtest"""
    from datetime import datetime, timedelta
    
    # Configuration
    SYMBOL = 'SPY'
    
    # Use last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    START_DATE = start_date.strftime('%Y-%m-%d')
    END_DATE = end_date.strftime('%Y-%m-%d')
    
    print(f"\n🎯 ORB STRATEGY BACKTEST (Enhanced Data Fetcher)")
    print(f"Symbol: {SYMBOL}")
    print(f"Period: {START_DATE} to {END_DATE}")
    print(f"Breakout Distance: 2.0 points")
    print(f"Risk/Reward Ratio: 2.0:1")
    print("")
    
    # Run backtest
    backtester = ORBBacktesterEnhanced(
        symbol=SYMBOL,
        start_date=START_DATE,
        end_date=END_DATE,
        breakout_distance=2.0,
        risk_reward_ratio=2.0,
        use_or_range_stops=True
    )
    
    try:
        stats = backtester.run_backtest()
        backtester.print_results(stats)
        
        if stats['total_trades'] > 0:
            backtester.export_trades()
    except Exception as e:
        print(f"\n❌ Backtest failed: {e}")
        print("\nTroubleshooting:")
        print("• Ensure data_fetcher.py is in the same directory")
        print("• Check internet connection")
        print("• Try a more recent date range (last 7 days)")


if __name__ == "__main__":
    main()