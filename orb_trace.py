"""
ORB Signal Trace - See Exactly Why Signals Are/Aren't Generated
Shows step-by-step what happens each day
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, time
import pytz

def trace_orb_signals(symbol='SPY', days_back=7, breakout_distance=2.0):
    """
    Detailed trace showing exactly what happens with ORB logic
    """
    
    print(f"\n{'='*80}")
    print(f"ORB SIGNAL TRACE - {symbol}")
    print(f"Breakout Distance: {breakout_distance} points")
    print(f"{'='*80}\n")
    
    # Fetch data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    ticker = yf.Ticker(symbol)
    df = ticker.history(
        start=start_date.strftime('%Y-%m-%d'),
        end=end_date.strftime('%Y-%m-%d'),
        interval='1m',
        prepost=False
    )
    
    if df.empty:
        print("❌ No data available")
        return
    
    # Convert timezone
    tz = pytz.timezone('America/New_York')
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    df.index = df.index.tz_convert(tz)
    
    # Split by day
    df['date'] = df.index.date
    
    total_signals = 0
    
    for date, day_df in df.groupby('date'):
        if len(day_df) < 20:
            continue
        
        print(f"\n{'='*80}")
        print(f"📅 {date} ({day_df.index[0].strftime('%A')})")
        print(f"{'='*80}")
        
        # Get OR
        try:
            or_bars = day_df.between_time('09:30:00', '09:45:00')
            
            if len(or_bars) == 0:
                print("❌ No OR data (market closed or pre-market only)")
                continue
            
            or_high = or_bars['High'].max()
            or_low = or_bars['Low'].min()
            or_mid = (or_high + or_low) / 2
            or_range = or_high - or_low
            
            print(f"\n📊 Opening Range (9:30-9:45 AM):")
            print(f"   High: ${or_high:.2f}")
            print(f"   Mid:  ${or_mid:.2f}")
            print(f"   Low:  ${or_low:.2f}")
            print(f"   Range: ${or_range:.2f}")
            
            # Get trading bars
            trading_bars = day_df[day_df.index.time >= time(9, 45)]
            
            if len(trading_bars) == 0:
                print("\n❌ No trading data after 9:45 AM")
                continue
            
            print(f"\n🔍 Trading Period Analysis (after 9:45 AM):")
            print(f"   Bars: {len(trading_bars)}")
            print(f"   Day High: ${trading_bars['High'].max():.2f}")
            print(f"   Day Low:  ${trading_bars['Low'].min():.2f}")
            
            # Simulate the strategy logic
            long_breakout_active = False
            short_breakout_active = False
            was_in_zone = True
            signals_today = []
            
            print(f"\n🎯 Signal Detection:")
            
            for idx, bar in trading_bars.iterrows():
                close = bar['Close']
                high = bar['High']
                low = bar['Low']
                
                # Check if in zone
                price_in_zone = close <= or_high and close >= or_low
                
                if price_in_zone and not was_in_zone:
                    print(f"   [{idx.strftime('%H:%M')}] Price back in zone: ${close:.2f}")
                    was_in_zone = True
                    long_breakout_active = False
                    short_breakout_active = False
                
                # LONG breakout
                if was_in_zone and not long_breakout_active:
                    if close >= or_high + breakout_distance:
                        print(f"   [{idx.strftime('%H:%M')}] 🔼 LONG BREAKOUT at ${close:.2f} (above ${or_high + breakout_distance:.2f})")
                        long_breakout_active = True
                        was_in_zone = False
                
                # SHORT breakout
                if was_in_zone and not short_breakout_active:
                    if close <= or_low - breakout_distance:
                        print(f"   [{idx.strftime('%H:%M')}] 🔽 SHORT BREAKOUT at ${close:.2f} (below ${or_low - breakout_distance:.2f})")
                        short_breakout_active = True
                        was_in_zone = False
                
                # LONG retest signal
                if long_breakout_active and low <= or_mid:
                    print(f"   [{idx.strftime('%H:%M')}] ✅ LONG SIGNAL - Retested midpoint at ${low:.2f} (mid: ${or_mid:.2f})")
                    signals_today.append(('LONG', idx.strftime('%H:%M'), or_mid))
                    long_breakout_active = False
                
                # SHORT retest signal
                if short_breakout_active and high >= or_mid:
                    print(f"   [{idx.strftime('%H:%M')}] ✅ SHORT SIGNAL - Retested midpoint at ${high:.2f} (mid: ${or_mid:.2f})")
                    signals_today.append(('SHORT', idx.strftime('%H:%M'), or_mid))
                    short_breakout_active = False
            
            # Summary for day
            if signals_today:
                print(f"\n🎯 Signals Generated: {len(signals_today)}")
                for sig_type, sig_time, entry in signals_today:
                    print(f"   • {sig_type} at {sig_time} - Entry: ${entry:.2f}")
                total_signals += len(signals_today)
            else:
                print(f"\n❌ No Signals Generated")
                
                # Explain why
                if not long_breakout_active and not short_breakout_active:
                    print(f"   Reason: No breakouts detected")
                    print(f"   Need: Close > ${or_high + breakout_distance:.2f} OR Close < ${or_low - breakout_distance:.2f}")
                else:
                    if long_breakout_active:
                        print(f"   Reason: LONG breakout occurred but no retest of midpoint (${or_mid:.2f})")
                    if short_breakout_active:
                        print(f"   Reason: SHORT breakout occurred but no retest of midpoint (${or_mid:.2f})")
        
        except Exception as e:
            print(f"❌ Error: {e}")
            continue
    
    print(f"\n{'='*80}")
    print(f"TOTAL SIGNALS ACROSS ALL DAYS: {total_signals}")
    print(f"{'='*80}\n")
    
    if total_signals == 0:
        print("💡 WHY NO SIGNALS?")
        print("-" * 80)
        print("The diagnostic shows breakouts ARE occurring, but signals require:")
        print("1. ✅ Price breaks out (closes beyond OR + distance)")
        print("2. ✅ Price comes BACK to retest the midpoint")
        print()
        print("If breakouts happened but no retests, it means:")
        print("• Strong trending moves (no pullbacks)")
        print("• Price stayed above/below after breakout")
        print()
        print("SOLUTIONS:")
        print("• Lower BREAKOUT_DISTANCE (try 1.0 or 1.5)")
        print("• Try symbols with more volatility (TSLA, NVDA)")
        print("• Test during earnings season (more back-and-forth)")
        print("• Accept that some weeks just don't have retests")
    
    return total_signals


def test_different_distances(symbol='SPY'):
    """
    Test different breakout distances to see which generates signals
    """
    
    print(f"\n{'='*80}")
    print(f"TESTING DIFFERENT BREAKOUT DISTANCES - {symbol}")
    print(f"{'='*80}\n")
    
    distances = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    
    results = []
    
    for dist in distances:
        print(f"Testing BREAKOUT_DISTANCE = {dist}...")
        signals = trace_orb_signals(symbol, days_back=7, breakout_distance=dist)
        results.append((dist, signals))
        print()
    
    print(f"\n{'='*80}")
    print(f"SUMMARY - Signals by Breakout Distance")
    print(f"{'='*80}")
    print(f"{'Distance':<12} {'Signals':<10} {'Comment'}")
    print(f"{'-'*80}")
    
    for dist, sigs in results:
        comment = ""
        if sigs == 0:
            comment = "Too strict"
        elif sigs >= 10:
            comment = "Too loose (many signals)"
        elif 3 <= sigs <= 7:
            comment = "✅ Good balance"
        else:
            comment = "Few signals"
        
        print(f"{dist:<12.1f} {sigs:<10} {comment}")
    
    print(f"{'='*80}\n")
    
    best = max(results, key=lambda x: x[1] if 3 <= x[1] <= 10 else 0)
    if best[1] > 0:
        print(f"💡 Recommended BREAKOUT_DISTANCE = {best[0]} ({best[1]} signals)")
    else:
        print(f"💡 No optimal distance found - market may be too quiet this week")


def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║              ORB SIGNAL TRACE TOOL                               ║
╚══════════════════════════════════════════════════════════════════╝

Shows exactly what happens each day and why signals are/aren't generated.

""")
    
    print("Choose analysis:")
    print("1. Detailed trace (SPY, 2.0 breakout distance)")
    print("2. Test different breakout distances (SPY)")
    print("3. Custom symbol trace")
    print()
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == '1':
        trace_orb_signals('SPY', days_back=7, breakout_distance=2.0)
    
    elif choice == '2':
        test_different_distances('SPY')
    
    elif choice == '3':
        symbol = input("Enter symbol: ").strip().upper()
        distance = float(input("Enter breakout distance (e.g., 2.0): ").strip())
        trace_orb_signals(symbol, days_back=7, breakout_distance=distance)
    
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()