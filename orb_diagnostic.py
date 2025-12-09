"""
ORB Diagnostic Tool
Analyzes why no trades were generated and shows detailed OR data
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, time
import pytz

def analyze_orb_opportunities(symbol='SPY', days_back=7):
    """
    Analyze recent days to see OR patterns and potential signals
    """
    
    print(f"\n{'='*70}")
    print(f"ORB DIAGNOSTIC ANALYSIS - {symbol}")
    print(f"{'='*70}\n")
    
    # Fetch recent data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    print(f"Fetching data from {start_date.date()} to {end_date.date()}...\n")
    
    ticker = yf.Ticker(symbol)
    df = ticker.history(
        start=start_date.strftime('%Y-%m-%d'),
        end=end_date.strftime('%Y-%m-%d'),
        interval='1m',
        prepost=False
    )
    
    if df.empty:
        print("❌ No data available. Try a different symbol or date range.")
        return
    
    # Convert timezone
    tz = pytz.timezone('America/New_York')
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    df.index = df.index.tz_convert(tz)
    
    print(f"✅ Retrieved {len(df)} bars\n")
    
    # Split by day
    df['date'] = df.index.date
    daily_groups = df.groupby('date')
    
    print(f"{'='*70}")
    print(f"DAILY OR ANALYSIS")
    print(f"{'='*70}\n")
    
    trading_days = 0
    days_with_breakouts = 0
    days_with_signals = 0
    
    for date, day_df in daily_groups:
        if len(day_df) < 20:  # Skip days with insufficient data
            continue
        
        trading_days += 1
        
        # Get OR period (9:30-9:45)
        try:
            or_bars = day_df.between_time('09:30:00', '09:45:00')
            
            if len(or_bars) == 0:
                print(f"{date}: No OR data (market closed or pre-market only)")
                continue
            
            or_high = or_bars['High'].max()
            or_low = or_bars['Low'].min()
            or_mid = (or_high + or_low) / 2
            or_range = or_high - or_low
            
            # Analyze rest of day
            trading_bars = day_df[day_df.index.time >= time(9, 45)]
            
            if len(trading_bars) == 0:
                continue
            
            day_high = trading_bars['High'].max()
            day_low = trading_bars['Low'].min()
            
            # Check for breakouts (2 points beyond OR)
            breakout_distance = 2.0
            long_breakout_level = or_high + breakout_distance
            short_breakout_level = or_low - breakout_distance
            
            had_long_breakout = day_high >= long_breakout_level
            had_short_breakout = day_low <= short_breakout_level
            
            # Check for retests
            had_long_retest = False
            had_short_retest = False
            
            if had_long_breakout:
                # Check if price came back to test midpoint
                for idx, bar in trading_bars.iterrows():
                    if bar['Close'] >= long_breakout_level:
                        # Now in breakout
                        remaining = trading_bars[trading_bars.index > idx]
                        if len(remaining) > 0 and remaining['Low'].min() <= or_mid:
                            had_long_retest = True
                            break
            
            if had_short_breakout:
                # Check if price came back to test midpoint
                for idx, bar in trading_bars.iterrows():
                    if bar['Close'] <= short_breakout_level:
                        # Now in breakout
                        remaining = trading_bars[trading_bars.index > idx]
                        if len(remaining) > 0 and remaining['High'].max() >= or_mid:
                            had_short_retest = True
                            break
            
            # Count
            if had_long_breakout or had_short_breakout:
                days_with_breakouts += 1
            
            if had_long_retest or had_short_retest:
                days_with_signals += 1
            
            # Print analysis
            print(f"📅 {date} ({day_df.index[0].strftime('%A')})")
            print(f"   OR: ${or_low:.2f} - ${or_high:.2f} (Mid: ${or_mid:.2f}, Range: ${or_range:.2f})")
            print(f"   Day: ${day_low:.2f} - ${day_high:.2f}")
            
            status_parts = []
            if had_long_breakout:
                status_parts.append(f"🔼 LONG breakout (>${long_breakout_level:.2f})")
            if had_short_breakout:
                status_parts.append(f"🔽 SHORT breakout (<${short_breakout_level:.2f})")
            if had_long_retest:
                status_parts.append("✅ LONG retest signal")
            if had_short_retest:
                status_parts.append("✅ SHORT retest signal")
            
            if not status_parts:
                status_parts.append("📊 Price stayed in/near OR zone (no breakout)")
            
            for part in status_parts:
                print(f"   {part}")
            
            print()
            
        except Exception as e:
            print(f"{date}: Error analyzing - {e}")
            continue
    
    # Summary
    print(f"{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Trading days analyzed:     {trading_days}")
    print(f"Days with breakouts:       {days_with_breakouts} ({days_with_breakouts/trading_days*100 if trading_days > 0 else 0:.1f}%)")
    print(f"Days with retest signals:  {days_with_signals} ({days_with_signals/trading_days*100 if trading_days > 0 else 0:.1f}%)")
    print(f"{'='*70}\n")
    
    if days_with_signals == 0:
        print("💡 WHY NO SIGNALS?")
        print("-" * 70)
        print("Possible reasons:")
        print("1. Market was ranging (stayed within OR boundaries)")
        print("2. Breakouts happened but no retest of midpoint")
        print("3. Low volatility week (narrow OR ranges)")
        print("4. Strong trending moves without pullbacks")
        print()
        print("SUGGESTIONS:")
        print("• Try BREAKOUT_DISTANCE = 1.0 (more sensitive)")
        print("• Test a more volatile symbol (TSLA, NVDA, etc.)")
        print("• Wait for higher volatility period")
        print("• Test on different weeks (some weeks just don't have signals)")
        print()
    else:
        print(f"✅ Strategy should have generated {days_with_signals} signal(s)")
        print("   If backtest showed 0 trades, there might be a logic issue.")
        print()


def compare_symbols():
    """Compare multiple symbols to find which have better OR opportunities"""
    
    symbols = ['SPY', 'QQQ', 'IWM', 'AAPL', 'TSLA', 'NVDA', 'AMD']
    
    print(f"\n{'='*70}")
    print(f"MULTI-SYMBOL OR COMPARISON")
    print(f"{'='*70}\n")
    
    results = []
    
    for symbol in symbols:
        try:
            print(f"Analyzing {symbol}...")
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                interval='1m',
                prepost=False
            )
            
            if df.empty:
                print(f"  ⚠️ No data\n")
                continue
            
            tz = pytz.timezone('America/New_York')
            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC')
            df.index = df.index.tz_convert(tz)
            
            df['date'] = df.index.date
            
            breakout_count = 0
            avg_or_range = []
            
            for date, day_df in df.groupby('date'):
                if len(day_df) < 20:
                    continue
                
                try:
                    or_bars = day_df.between_time('09:30:00', '09:45:00')
                    if len(or_bars) == 0:
                        continue
                    
                    or_high = or_bars['High'].max()
                    or_low = or_bars['Low'].min()
                    or_range = or_high - or_low
                    avg_or_range.append(or_range)
                    
                    trading_bars = day_df[day_df.index.time >= time(9, 45)]
                    if len(trading_bars) == 0:
                        continue
                    
                    day_high = trading_bars['High'].max()
                    day_low = trading_bars['Low'].min()
                    
                    if day_high >= or_high + 2.0 or day_low <= or_low - 2.0:
                        breakout_count += 1
                
                except:
                    continue
            
            avg_range = sum(avg_or_range) / len(avg_or_range) if avg_or_range else 0
            
            results.append({
                'symbol': symbol,
                'breakouts': breakout_count,
                'avg_or_range': avg_range,
                'days': len(avg_or_range)
            })
            
            print(f"  ✓ {breakout_count} breakouts, Avg OR: ${avg_range:.2f}\n")
            
        except Exception as e:
            print(f"  ⚠️ Error: {e}\n")
    
    # Print comparison table
    print(f"\n{'='*70}")
    print(f"COMPARISON TABLE")
    print(f"{'='*70}")
    print(f"{'Symbol':<8} {'Breakouts':<12} {'Avg OR Range':<15} {'Days':<8}")
    print(f"{'-'*70}")
    
    for r in sorted(results, key=lambda x: x['breakouts'], reverse=True):
        print(f"{r['symbol']:<8} {r['breakouts']:<12} ${r['avg_or_range']:<14.2f} {r['days']:<8}")
    
    print(f"{'='*70}\n")
    
    if results:
        best = max(results, key=lambda x: x['breakouts'])
        print(f"💡 Best symbol for ORB strategy: {best['symbol']} ({best['breakouts']} breakouts)")
        print(f"   Try backtesting with: SYMBOL = '{best['symbol']}'")
    print()


def main():
    """Main diagnostic menu"""
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║              ORB STRATEGY DIAGNOSTIC TOOL                        ║
╚══════════════════════════════════════════════════════════════════╝

This tool helps you understand why the backtest might show no trades
and find symbols/periods with better ORB opportunities.

""")
    
    print("Choose analysis:")
    print("1. Detailed single symbol analysis (SPY)")
    print("2. Compare multiple symbols")
    print("3. Custom symbol analysis")
    print()
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == '1':
        analyze_orb_opportunities('SPY', days_back=7)
    
    elif choice == '2':
        compare_symbols()
    
    elif choice == '3':
        symbol = input("Enter symbol (e.g., TSLA): ").strip().upper()
        if symbol:
            analyze_orb_opportunities(symbol, days_back=7)
    
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()