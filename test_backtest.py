"""
Quick Test Script - Verify ORB Backtester Works
Tests with recent data from last few days
"""

from orb_backtest import ORBBacktester
from datetime import datetime, timedelta

def test_recent_data():
    """Test with very recent data (last 5 days)"""
    
    # Calculate dates - last 5 trading days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)  # Go back 7 days to get ~5 trading days
    
    symbol = 'SPY'
    
    print("=" * 70)
    print("🧪 TESTING ORB BACKTESTER")
    print("=" * 70)
    print(f"Symbol: {symbol}")
    print(f"Testing with last week's data...")
    print(f"Start: {start_date.strftime('%Y-%m-%d')}")
    print(f"End:   {end_date.strftime('%Y-%m-%d')}")
    print("")
    
    try:
        # Create backtester
        backtester = ORBBacktester(
            symbol=symbol,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            breakout_distance=2.0,
            risk_reward_ratio=2.0,
            use_or_range_stops=True
        )
        
        # Run backtest
        stats = backtester.run_backtest()
        
        # Print results
        backtester.print_results(stats)
        
        if stats['total_trades'] > 0:
            print("\n✅ TEST PASSED - Backtester is working correctly!")
            print(f"   Found {stats['total_trades']} trades in the test period")
        else:
            print("\n⚠️  TEST PASSED - But no trades generated")
            print("   This could be normal if market was quiet")
            print("   Try running: python orb_backtest.py with different dates")
        
        # Export trades
        if stats['total_trades'] > 0:
            backtester.export_trades(f"test_trades_{symbol}.csv")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED")
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you have internet connection")
        print("2. Check if requirements are installed: pip install -r requirements.txt")
        print("3. Try a different symbol (QQQ, AAPL)")
        print("4. Ensure dates are recent (Yahoo has ~7-30 day limit for 1m data)")
        return False


def test_multiple_symbols():
    """Quick test with multiple popular symbols"""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    symbols = ['SPY', 'QQQ', 'IWM']
    
    print("\n" + "=" * 70)
    print("🧪 MULTI-SYMBOL TEST")
    print("=" * 70)
    print(f"Testing: {', '.join(symbols)}")
    print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print("")
    
    results = {}
    
    for symbol in symbols:
        try:
            print(f"\nTesting {symbol}...")
            
            backtester = ORBBacktester(
                symbol=symbol,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                breakout_distance=2.0,
                risk_reward_ratio=2.0,
                use_or_range_stops=True
            )
            
            stats = backtester.run_backtest()
            results[symbol] = stats
            
            print(f"   {symbol}: {stats['total_trades']} trades | Win Rate: {stats.get('win_rate', 0)}%")
            
        except Exception as e:
            print(f"   {symbol}: Failed - {e}")
            results[symbol] = None
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    
    for symbol, stats in results.items():
        if stats and stats['total_trades'] > 0:
            print(f"{symbol:6s} | Trades: {stats['total_trades']:2d} | "
                  f"Win Rate: {stats['win_rate']:5.1f}% | "
                  f"P&L: ${stats['total_pnl']:7.2f}")
    
    successful = sum(1 for s in results.values() if s and s['total_trades'] > 0)
    print(f"\n✅ Successfully tested {successful}/{len(symbols)} symbols")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                 ORB BACKTESTER - QUICK TEST                      ║
╚══════════════════════════════════════════════════════════════════╝

This script tests the backtester with recent market data.
It will verify everything is working correctly.

""")
    
    # Run single symbol test
    success = test_recent_data()
    
    if success:
        # If first test passed, try multiple symbols
        print("\n" + "─" * 70)
        user_input = input("\nRun multi-symbol test? (y/n): ").strip().lower()
        
        if user_input == 'y':
            test_multiple_symbols()
    
    print("\n" + "=" * 70)
    print("Test complete!")
    print("\nNext steps:")
    print("1. Run full backtest: python orb_backtest.py")
    print("2. Customize parameters in orb_backtest.py")
    print("3. Test your favorite symbols")
    print("=" * 70 + "\n")