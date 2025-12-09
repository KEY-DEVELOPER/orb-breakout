"""
ORB Strategy Backtester
Test the Opening Range Breakout strategy on historical data
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
import json

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


class ORBBacktester:
    """
    Backtest the ORB strategy on historical data
    """
    
    def __init__(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        breakout_distance: float = 2.0,
        timezone: str = "America/New_York",
        risk_reward_ratio: float = 2.0,  # 2:1 R:R ratio
        use_or_range_stops: bool = True,  # Use OR levels for stop loss
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
    
    def fetch_data(self) -> pd.DataFrame:
        """Fetch historical intraday data"""
        print(f"Fetching data for {self.symbol}...")
        
        ticker = yf.Ticker(self.symbol)
        
        # Calculate date range
        start = pd.to_datetime(self.start_date)
        end = pd.to_datetime(self.end_date)
        
        # Yahoo Finance limits 1m data to 7 days per request
        # We'll fetch in 5-day chunks to be safe
        all_data = []
        current = start
        
        while current < end:
            chunk_end = min(current + timedelta(days=5), end)
            
            print(f"  Fetching {current.date()} to {chunk_end.date()}...")
            
            try:
                df_chunk = ticker.history(
                    start=current,
                    end=chunk_end,
                    interval='1m'
                )
                
                if not df_chunk.empty:
                    all_data.append(df_chunk)
                else:
                    print(f"  ⚠️ No data for this period")
                    
            except Exception as e:
                print(f"  ⚠️ Error fetching chunk: {e}")
            
            current = chunk_end
        
        if not all_data:
            raise ValueError(f"No data retrieved for {self.symbol}. Note: Yahoo Finance only provides 1-minute data for the last 7-30 days. Try a more recent date range.")
        
        # Combine all chunks
        df = pd.concat(all_data)
        df.index = df.index.tz_convert(self.timezone)
        
        print(f"✅ Retrieved {len(df)} bars from {len(all_data)} chunks")
        return df
    
    def get_daily_data(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Split data by trading day"""
        df['date'] = df.index.date
        
        daily_data = {}
        for date, group in df.groupby('date'):
            # Only include days with sufficient data
            if len(group) > 20:  # At least 20 bars
                daily_data[str(date)] = group
        
        return daily_data
    
    def capture_opening_range(self, df: pd.DataFrame) -> Tuple[float, float, float]:
        """
        Capture OR high/low from 9:30-9:45
        Returns (or_high, or_low, or_mid)
        """
        or_bars = df.between_time('09:30:00', '09:45:00')
        
        if len(or_bars) == 0:
            return None, None, None
        
        or_high = or_bars['High'].max()
        or_low = or_bars['Low'].min()
        or_mid = (or_high + or_low) / 2
        
        return or_high, or_low, or_mid
    
    def simulate_day(self, date: str, df: pd.DataFrame) -> List[BacktestTrade]:
        """
        Simulate trading for one day with OR-based stops and 2:1 R:R
        Returns list of trades
        """
        trades = []
        
        # Capture OR
        or_high, or_low, or_mid = self.capture_opening_range(df)
        
        if or_high is None:
            return trades
        
        or_range = or_high - or_low
        
        # Filter for trading hours (after 9:45)
        trading_bars = df[df.index.time >= time(9, 45)]
        
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
            
            # Check if in trade - manage exit
            if in_trade and current_trade:
                
                if current_trade.direction == 'LONG':
                    # Check stop loss (OR low)
                    if low <= current_trade.stop_loss:
                        current_trade.exit_price = current_trade.stop_loss
                        current_trade.exit_time = idx.strftime('%H:%M:%S')
                        current_trade.exit_reason = 'Stop Loss'
                        in_trade = False
                    
                    # Check profit target (2:1 R:R)
                    elif high >= current_trade.profit_target:
                        current_trade.exit_price = current_trade.profit_target
                        current_trade.exit_time = idx.strftime('%H:%M:%S')
                        current_trade.exit_reason = 'Profit Target (2:1)'
                        in_trade = False
                
                elif current_trade.direction == 'SHORT':
                    # Check stop loss (OR high)
                    if high >= current_trade.stop_loss:
                        current_trade.exit_price = current_trade.stop_loss
                        current_trade.exit_time = idx.strftime('%H:%M:%S')
                        current_trade.exit_reason = 'Stop Loss'
                        in_trade = False
                    
                    # Check profit target (2:1 R:R)
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
            
            # Not in trade - look for signals
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
                
                # Check for retest entry - LONG
                if long_breakout_active and low <= or_mid:
                    # Entry at midpoint
                    entry_price = or_mid
                    
                    # Stop loss at OR low (or slightly below)
                    if self.use_or_range_stops:
                        stop_loss = or_low
                    else:
                        stop_loss = entry_price - or_range  # Use OR range as risk
                    
                    # Calculate risk and target with 2:1 R:R
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
                
                # Check for retest entry - SHORT
                if short_breakout_active and high >= or_mid:
                    # Entry at midpoint
                    entry_price = or_mid
                    
                    # Stop loss at OR high (or slightly above)
                    if self.use_or_range_stops:
                        stop_loss = or_high
                    else:
                        stop_loss = entry_price + or_range  # Use OR range as risk
                    
                    # Calculate risk and target with 2:1 R:R
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
        
        # Close any open trade at end of day
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
        """
        Run the backtest
        Returns summary statistics
        """
        # Fetch data
        self.df = self.fetch_data()
        
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
        stats = self.calculate_statistics()
        
        return stats
    
    def calculate_statistics(self) -> Dict:
        """Calculate backtest statistics"""
        if not self.trades:
            return {
                'symbol': self.symbol,
                'start_date': self.start_date,
                'end_date': self.end_date,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'breakeven_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 'N/A',
                'max_drawdown': 0,
                'long_trades': 0,
                'long_win_rate': 0,
                'short_trades': 0,
                'short_win_rate': 0,
                'message': 'No trades generated'
            }
        
        df_trades = pd.DataFrame([asdict(t) for t in self.trades])
        
        total_trades = len(df_trades)
        winning_trades = len(df_trades[df_trades['pnl'] > 0])
        losing_trades = len(df_trades[df_trades['pnl'] < 0])
        breakeven_trades = len(df_trades[df_trades['pnl'] == 0])
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        avg_win = df_trades[df_trades['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = df_trades[df_trades['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        
        total_pnl = df_trades['pnl'].sum()
        avg_pnl = df_trades['pnl'].mean()
        
        profit_factor = abs(df_trades[df_trades['pnl'] > 0]['pnl'].sum() / 
                           df_trades[df_trades['pnl'] < 0]['pnl'].sum()) if losing_trades > 0 else float('inf')
        
        # Calculate max drawdown
        df_trades['cumulative_pnl'] = df_trades['pnl'].cumsum()
        df_trades['running_max'] = df_trades['cumulative_pnl'].cummax()
        df_trades['drawdown'] = df_trades['running_max'] - df_trades['cumulative_pnl']
        max_drawdown = df_trades['drawdown'].max()
        
        # Calculate average R:R achieved (for winning trades)
        df_trades['risk'] = df_trades.apply(
            lambda row: row['entry_price'] - row['stop_loss'] if row['direction'] == 'LONG' 
            else row['stop_loss'] - row['entry_price'], axis=1
        )
        df_trades['rr_achieved'] = df_trades.apply(
            lambda row: abs(row['pnl'] / row['risk']) if row['risk'] > 0 else 0, axis=1
        )
        avg_rr_achieved = df_trades[df_trades['pnl'] > 0]['rr_achieved'].mean() if winning_trades > 0 else 0
        
        # Long vs Short performance
        long_trades = df_trades[df_trades['direction'] == 'LONG']
        short_trades = df_trades[df_trades['direction'] == 'SHORT']
        
        stats = {
            'symbol': self.symbol,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'breakeven_trades': breakeven_trades,
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2),
            'avg_pnl': round(avg_pnl, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'avg_rr_achieved': avg_rr_achieved,
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 'N/A',
            'max_drawdown': round(max_drawdown, 2),
            'long_trades': len(long_trades),
            'long_win_rate': round(len(long_trades[long_trades['pnl'] > 0]) / len(long_trades) * 100, 2) if len(long_trades) > 0 else 0,
            'short_trades': len(short_trades),
            'short_win_rate': round(len(short_trades[short_trades['pnl'] > 0]) / len(short_trades) * 100, 2) if len(short_trades) > 0 else 0,
        }
        
        return stats
    
    def print_results(self, stats: Dict):
        """Print backtest results"""
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)
        print(f"Symbol:        {stats['symbol']}")
        print(f"Period:        {stats['start_date']} to {stats['end_date']}")
        print(f"Total Trades:  {stats['total_trades']}")
        print(f"")
        print(f"Winning:       {stats['winning_trades']} ({stats['win_rate']}%)")
        print(f"Losing:        {stats['losing_trades']}")
        print(f"Breakeven:     {stats['breakeven_trades']}")
        print(f"")
        print(f"Total P&L:     ${stats['total_pnl']}")
        print(f"Avg P&L:       ${stats['avg_pnl']}")
        print(f"Avg Win:       ${stats['avg_win']}")
        print(f"Avg Loss:      ${stats['avg_loss']}")
        
        # Show average R:R achieved
        if 'avg_rr_achieved' in stats:
            print(f"Avg R:R:       {stats['avg_rr_achieved']:.2f}:1")
        
        print(f"")
        print(f"Profit Factor: {stats['profit_factor']}")
        print(f"Max Drawdown:  ${stats['max_drawdown']}")
        print(f"")
        print(f"LONG Trades:   {stats['long_trades']} ({stats['long_win_rate']}% win rate)")
        print(f"SHORT Trades:  {stats['short_trades']} ({stats['short_win_rate']}% win rate)")
        print("=" * 60)
        
        # Show sample trades if available
        if self.trades:
            print("\n📊 SAMPLE TRADES (First 5):")
            print("-" * 60)
            for i, trade in enumerate(self.trades[:5]):
                risk = trade.entry_price - trade.stop_loss if trade.direction == 'LONG' else trade.stop_loss - trade.entry_price
                reward = trade.profit_target - trade.entry_price if trade.direction == 'LONG' else trade.entry_price - trade.profit_target
                rr_setup = reward / risk if risk > 0 else 0
                
                print(f"\n{i+1}. {trade.direction} on {trade.date}")
                print(f"   Entry: ${trade.entry_price:.2f} | Stop: ${trade.stop_loss:.2f} | Target: ${trade.profit_target:.2f}")
                print(f"   Risk: ${risk:.2f} | Reward: ${reward:.2f} | Setup R:R: {rr_setup:.2f}:1")
                print(f"   Exit: ${trade.exit_price:.2f} ({trade.exit_reason}) | P&L: ${trade.pnl:.2f}")
            print("-" * 60)
    
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
    """Run backtest example"""
    from datetime import datetime, timedelta
    
    # Configuration
    SYMBOL = 'SPY'
    
    # Calculate recent dates (last 7 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    START_DATE = start_date.strftime('%Y-%m-%d')
    END_DATE = end_date.strftime('%Y-%m-%d')
    
    # Strategy parameters
    BREAKOUT_DISTANCE = 2.0       # Points beyond OR to trigger breakout
    RISK_REWARD_RATIO = 2.0       # 2:1 Risk/Reward ratio
    USE_OR_RANGE_STOPS = True     # Stop loss at OR low (long) or OR high (short)
    
    print(f"\n🎯 ORB STRATEGY BACKTEST")
    print(f"Symbol: {SYMBOL}")
    print(f"Period: {START_DATE} to {END_DATE} (last 7 days)")
    print(f"Breakout Distance: {BREAKOUT_DISTANCE} points")
    print(f"Risk/Reward Ratio: {RISK_REWARD_RATIO}:1")
    print(f"Stop Loss: OR boundary (High for shorts, Low for longs)")
    print(f"Target: Entry + (Risk × {RISK_REWARD_RATIO})")
    print("")
    print("⚠️  Note: Yahoo Finance provides 1-minute data for ~7-30 days only")
    print("    Using most recent data available")
    print("")
    
    # Run backtest
    backtester = ORBBacktester(
        symbol=SYMBOL,
        start_date=START_DATE,
        end_date=END_DATE,
        breakout_distance=BREAKOUT_DISTANCE,
        risk_reward_ratio=RISK_REWARD_RATIO,
        use_or_range_stops=USE_OR_RANGE_STOPS
    )
    
    stats = backtester.run_backtest()
    backtester.print_results(stats)
    
    # Export trades if any
    if stats['total_trades'] > 0:
        backtester.export_trades()
    else:
        print("\n💡 No trades generated. This can happen if:")
        print("   • Market was quiet (low volatility)")
        print("   • No breakouts occurred during the period")
        print("   • Try testing a different symbol or longer period")
    
    print("\n💡 Tips:")
    print("   • Adjust BREAKOUT_DISTANCE (1.0-3.0) to tune sensitivity")
    print("   • Try RISK_REWARD_RATIO of 1.5, 2.0, or 3.0")
    print("   • Test different symbols: QQQ, AAPL, TSLA, etc.")
    print("   • Use recent dates (last 7-14 days) for 1-minute data")
    print("")


if __name__ == "__main__":
    main()