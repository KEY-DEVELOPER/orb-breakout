"""
ORB Scanner Web Dashboard
Real-time monitoring interface with live updates
"""

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from threading import Thread
import time
from datetime import datetime
from orb_scanner import ORBScanner, ORBSignal
from typing import List
import pytz

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global scanner instance
scanner = None
scanner_thread = None


class WebDashboardScanner(ORBScanner):
    """Scanner that emits updates to web dashboard"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_update = datetime.now(self.timezone)
    
    def scan_all_symbols(self) -> List[ORBSignal]:
        """Override to emit updates via SocketIO"""
        signals = super().scan_all_symbols()
        
        # Emit new signals
        for signal in signals:
            socketio.emit('new_signal', {
                'symbol': signal.symbol,
                'type': signal.signal_type,
                'timestamp': signal.timestamp.isoformat(),
                'current_price': round(signal.current_price, 2),
                'or_high': round(signal.or_high, 2),
                'or_mid': round(signal.or_mid, 2),
                'or_low': round(signal.or_low, 2),
            })
        
        # Emit status update
        self.last_update = datetime.now(self.timezone)
        socketio.emit('status_update', self.get_status_dict())
        
        return signals
    
    def get_status_dict(self):
        """Get status as dictionary for JSON"""
        status = {
            'last_update': self.last_update.isoformat(),
            'trading_hours': self.is_trading_hours(),
            'symbols': {}
        }
        
        for symbol in self.symbols:
            or_info = self.or_data[symbol]
            state = self.breakout_state[symbol]
            
            symbol_status = {
                'or_captured': or_info['captured'],
                'or_high': or_info['high'],
                'or_low': or_info['low'],
                'or_mid': or_info['mid'],
                'long_breakout_active': state['long_breakout_active'],
                'short_breakout_active': state['short_breakout_active'],
                'signals_count': len(self.signals_today[symbol]),
                'signals': [
                    {
                        'type': s.signal_type,
                        'timestamp': s.timestamp.isoformat(),
                        'price': round(s.current_price, 2)
                    }
                    for s in self.signals_today[symbol]
                ]
            }
            
            status['symbols'][symbol] = symbol_status
        
        return status


def scanner_background_task():
    """Run scanner in background thread"""
    global scanner
    
    print("Scanner background task started")
    
    while True:
        try:
            if scanner and scanner.is_trading_hours():
                scanner.scan_all_symbols()
            time.sleep(scanner.check_interval if scanner else 60)
        except Exception as e:
            print(f"Error in scanner task: {e}")
            time.sleep(60)


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/status')
def get_status():
    """Get current status"""
    if scanner:
        return jsonify(scanner.get_status_dict())
    return jsonify({'error': 'Scanner not initialized'})


@app.route('/api/start')
def start_scanner():
    """Start the scanner"""
    global scanner, scanner_thread
    
    if scanner is None:
        # Define symbols
        symbols = [
            'SPY', 'QQQ', 'DIA', 'IWM',
            'AAPL', 'MSFT', 'TSLA', 'NVDA', 'GOOGL', 'AMZN',
            'GLD', 'SLV', 'USO', 'UNG', 'VXX'
        ]
        
        scanner = WebDashboardScanner(
            symbols=symbols,
            breakout_distance=2.0,
            timezone="America/New_York",
            check_interval=60
        )
        
        scanner_thread = Thread(target=scanner_background_task, daemon=True)
        scanner_thread.start()
        
        return jsonify({'status': 'started', 'symbols': len(symbols)})
    
    return jsonify({'status': 'already_running'})


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    if scanner:
        socketio.emit('status_update', scanner.get_status_dict())


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')


def create_dashboard_html():
    """Create HTML template for dashboard"""
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>ORB Scanner Dashboard</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 30px;
        }
        
        h1 {
            color: #667eea;
            margin-bottom: 10px;
        }
        
        .status-bar {
            display: flex;
            gap: 20px;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        
        .status-item {
            padding: 10px 20px;
            background: #f7f9fc;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        
        .status-item strong {
            color: #667eea;
        }
        
        .signals-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .signal-card {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
            animation: slideIn 0.3s ease-out;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(-20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .signal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .signal-symbol {
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }
        
        .signal-type {
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 14px;
        }
        
        .signal-type.LONG {
            background: #10b981;
            color: white;
        }
        
        .signal-type.SHORT {
            background: #ef4444;
            color: white;
        }
        
        .signal-details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        
        .signal-detail {
            padding: 10px;
            background: #f7f9fc;
            border-radius: 8px;
        }
        
        .signal-detail label {
            display: block;
            font-size: 12px;
            color: #666;
            margin-bottom: 5px;
        }
        
        .signal-detail value {
            display: block;
            font-size: 18px;
            font-weight: bold;
            color: #333;
        }
        
        .symbols-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 15px;
        }
        
        .symbol-card {
            background: white;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        }
        
        .symbol-card.active {
            border-left: 4px solid #10b981;
        }
        
        .symbol-card.inactive {
            opacity: 0.6;
        }
        
        .symbol-name {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
        }
        
        .symbol-status {
            font-size: 14px;
            color: #666;
            margin-bottom: 8px;
        }
        
        .or-levels {
            display: flex;
            gap: 10px;
            font-size: 12px;
            margin-top: 10px;
        }
        
        .or-level {
            padding: 5px 10px;
            background: #f7f9fc;
            border-radius: 5px;
        }
        
        .loading {
            text-align: center;
            padding: 50px;
            color: white;
            font-size: 18px;
        }
        
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 10px;
        }
        
        .badge.watching {
            background: #fbbf24;
            color: #78350f;
        }
        
        .badge.breakout {
            background: #10b981;
            color: white;
        }
        
        h2 {
            color: white;
            margin: 30px 0 20px 0;
            font-size: 24px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 ORB Breakout Scanner</h1>
            <p>Real-time monitoring of Opening Range breakouts and retests</p>
            <div class="status-bar">
                <div class="status-item">
                    <strong>Status:</strong> <span id="connection-status">Connecting...</span>
                </div>
                <div class="status-item">
                    <strong>Last Update:</strong> <span id="last-update">-</span>
                </div>
                <div class="status-item">
                    <strong>Trading Hours:</strong> <span id="trading-hours">-</span>
                </div>
                <div class="status-item">
                    <strong>Total Signals:</strong> <span id="total-signals">0</span>
                </div>
            </div>
        </div>
        
        <h2>📢 Recent Signals</h2>
        <div class="signals-container" id="signals-container">
            <div class="loading">Waiting for signals...</div>
        </div>
        
        <h2>📊 Monitored Symbols</h2>
        <div class="symbols-grid" id="symbols-grid">
            <div class="loading">Loading symbols...</div>
        </div>
    </div>
    
    <script>
        const socket = io();
        let allSignals = [];
        let symbolsData = {};
        
        socket.on('connect', function() {
            document.getElementById('connection-status').textContent = 'Connected ✅';
            document.getElementById('connection-status').style.color = '#10b981';
            
            // Request initial status
            fetch('/api/start')
                .then(r => r.json())
                .then(data => console.log('Scanner started:', data));
        });
        
        socket.on('disconnect', function() {
            document.getElementById('connection-status').textContent = 'Disconnected ❌';
            document.getElementById('connection-status').style.color = '#ef4444';
        });
        
        socket.on('new_signal', function(signal) {
            console.log('New signal:', signal);
            allSignals.unshift(signal);
            
            // Play sound or show notification
            if (Notification.permission === "granted") {
                new Notification(`${signal.type} Signal: ${signal.symbol}`, {
                    body: `Price: $${signal.current_price} | Entry: $${signal.or_mid}`,
                    icon: signal.type === 'LONG' ? '🟢' : '🔴'
                });
            }
            
            updateSignalsDisplay();
        });
        
        socket.on('status_update', function(status) {
            console.log('Status update:', status);
            
            // Update header
            const lastUpdate = new Date(status.last_update);
            document.getElementById('last-update').textContent = lastUpdate.toLocaleTimeString();
            document.getElementById('trading-hours').textContent = status.trading_hours ? 'Yes ✅' : 'No ⏸️';
            
            // Count total signals
            let totalSignals = 0;
            for (const symbol in status.symbols) {
                totalSignals += status.symbols[symbol].signals_count;
            }
            document.getElementById('total-signals').textContent = totalSignals;
            
            symbolsData = status.symbols;
            updateSymbolsDisplay();
        });
        
        function updateSignalsDisplay() {
            const container = document.getElementById('signals-container');
            
            if (allSignals.length === 0) {
                container.innerHTML = '<div class="loading">No signals yet today</div>';
                return;
            }
            
            container.innerHTML = allSignals.slice(0, 20).map(signal => `
                <div class="signal-card">
                    <div class="signal-header">
                        <div class="signal-symbol">${signal.symbol}</div>
                        <div class="signal-type ${signal.type}">${signal.type}</div>
                    </div>
                    <div class="signal-details">
                        <div class="signal-detail">
                            <label>Current Price</label>
                            <value>$${signal.current_price}</value>
                        </div>
                        <div class="signal-detail">
                            <label>Entry (Mid)</label>
                            <value>$${signal.or_mid}</value>
                        </div>
                        <div class="signal-detail">
                            <label>OR High</label>
                            <value>$${signal.or_high}</value>
                        </div>
                        <div class="signal-detail">
                            <label>OR Low</label>
                            <value>$${signal.or_low}</value>
                        </div>
                    </div>
                    <div style="margin-top: 10px; font-size: 12px; color: #666;">
                        ${new Date(signal.timestamp).toLocaleString()}
                    </div>
                </div>
            `).join('');
        }
        
        function updateSymbolsDisplay() {
            const container = document.getElementById('symbols-grid');
            
            if (Object.keys(symbolsData).length === 0) {
                container.innerHTML = '<div class="loading">Loading symbols...</div>';
                return;
            }
            
            container.innerHTML = Object.entries(symbolsData).map(([symbol, data]) => {
                let statusText = '';
                let statusClass = 'inactive';
                let badge = '';
                
                if (!data.or_captured) {
                    statusText = '⏳ Waiting for OR';
                } else {
                    if (data.long_breakout_active) {
                        statusText = '✅ LONG breakout - watching for retest';
                        statusClass = 'active';
                        badge = '<span class="badge breakout">LONG ACTIVE</span>';
                    } else if (data.short_breakout_active) {
                        statusText = '✅ SHORT breakout - watching for retest';
                        statusClass = 'active';
                        badge = '<span class="badge breakout">SHORT ACTIVE</span>';
                    } else {
                        statusText = '👀 Watching for breakout';
                        statusClass = '';
                        badge = '<span class="badge watching">WATCHING</span>';
                    }
                }
                
                const orLevels = data.or_captured ? `
                    <div class="or-levels">
                        <div class="or-level">H: $${data.or_high?.toFixed(2)}</div>
                        <div class="or-level">M: $${data.or_mid?.toFixed(2)}</div>
                        <div class="or-level">L: $${data.or_low?.toFixed(2)}</div>
                    </div>
                ` : '';
                
                return `
                    <div class="symbol-card ${statusClass}">
                        <div class="symbol-name">
                            ${symbol}
                            ${badge}
                        </div>
                        <div class="symbol-status">${statusText}</div>
                        ${data.signals_count > 0 ? `<div style="color: #10b981; font-weight: bold; margin-top: 5px;">📢 ${data.signals_count} signal(s) today</div>` : ''}
                        ${orLevels}
                    </div>
                `;
            }).join('');
        }
        
        // Request notification permission
        if (Notification.permission === "default") {
            Notification.requestPermission();
        }
    </script>
</body>
</html>"""
    
    return html_content


def main():
    """Run the web dashboard"""
    import os
    
    # Create templates directory
    templates_dir = 'templates'
    os.makedirs(templates_dir, exist_ok=True)
    
    # Write dashboard HTML with UTF-8 encoding
    with open(f'{templates_dir}/dashboard.html', 'w', encoding='utf-8') as f:
        f.write(create_dashboard_html())
    
    print("\n🌐 ORB Scanner Web Dashboard")
    print("=" * 50)
    print("Starting server...")
    print("\nOpen your browser and go to:")
    print("👉 http://localhost:5000")
    print("\nPress Ctrl+C to stop")
    print("=" * 50 + "\n")
    
    # Run Flask app
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)


if __name__ == "__main__":
    main()