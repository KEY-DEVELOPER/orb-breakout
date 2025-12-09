"""ORB Scanner - Fused Pro+Control Dashboard

Fuses:
- Pro dashboard look & layout (v3.0 style)
- Control dashboard features (symbol management, Telegram/Email notifications, connection tests)
Adds:
- Market status for multiple sessions/timezones with countdowns
- Click a symbol card to open a modal with deeper stats + intraday chart

Run:
  python fused_pro_control_dashboard.py
Then open:
  http://localhost:5003

Notes:
- Requires orb_scanner.py providing ORBScanner, ORBSignal
- Uses yfinance for data
"""

from __future__ import annotations

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from threading import Thread
import time
from datetime import datetime, timedelta, time as dtime
from typing import List, Dict, Optional, Any
import asyncio
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pytz
import yfinance as yf
import logging

# Suppress yfinance warnings and errors for cleaner logs
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.getLogger('peewee').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)

from orb_scanner import ORBScanner, ORBSignal
import os
import json

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "dashboard_config.json")

def load_persisted_config() -> Dict[str, Any]:
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        print(f'⚠️ Failed to load persisted config: {e}')
    return {}

def persist_config(config: Dict[str, Any]) -> None:
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f'⚠️ Failed to persist config: {e}')



# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "orb-scanner-fused-2025"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# -----------------------------------------------------------------------------
# Global state
# -----------------------------------------------------------------------------
scanner: Optional["FusedDashboardScanner"] = None
scanner_thread: Optional[Thread] = None

settings: Dict[str, Any] = {
    "breakout_distance": 2.0,
    "check_interval": 60,
    "sound_alerts": True,
    "desktop_notifications": True,

    # Notifications
    "telegram_enabled": False,
    "telegram_bot_token": "",
    "telegram_chat_id": "",

    "email_enabled": False,
    "email_smtp_server": "smtp.gmail.com",
    "email_smtp_port": 587,
    "email_sender": "",
    "email_password": "",
    "email_recipient": "",

    # UI toggles
    "dark_mode": True,
}

_persisted = load_persisted_config()
if isinstance(_persisted.get('settings'), dict):
    settings.update(_persisted['settings'])


active_symbols: List[str] = [
    "SPY", "QQQ", "DIA", "IWM",
    "AAPL", "MSFT", "TSLA", "NVDA", "GOOGL", "AMZN",
    "GLD", "SLV", "USO", "UNG", "VXX",
]

if isinstance(_persisted.get('active_symbols'), list) and _persisted['active_symbols']:
    active_symbols = [str(s).upper() for s in _persisted['active_symbols']]


# -----------------------------------------------------------------------------
# Notifications
# -----------------------------------------------------------------------------
class NotificationManager:
    @staticmethod
    async def send_telegram(token: str, chat_id: str, message: str) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
                async with session.post(url, json=payload) as response:
                    return response.status == 200
        except Exception as e:
            print(f"Telegram error: {e}")
            return False

    @staticmethod
    def send_email(
        smtp_server: str,
        smtp_port: int,
        sender: str,
        password: str,
        recipient: str,
        subject: str,
        body_html: str,
    ) -> bool:
        try:
            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.attach(MIMEText(body_html, "html"))

            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"Email error: {e}")
            return False

    @staticmethod
    def format_signal_message(signal: ORBSignal, format_type: str = "telegram") -> str:
        entry = round(signal.or_mid, 2)
        stop = round(signal.or_low if signal.signal_type == "LONG" else signal.or_high, 2)
        risk = abs(entry - stop)
        target = round(entry + risk * 2 if signal.signal_type == "LONG" else entry - risk * 2, 2)

        if format_type == "telegram":
            emoji = "🟢" if signal.signal_type == "LONG" else "🔴"
            return f"""
{emoji} <b>{signal.signal_type} SIGNAL - {signal.symbol}</b>

<b>ENTER NOW at ${entry}</b>
Stop Loss: ${stop}
Target: ${target}
Risk/Reward: 2:1

OR Range: ${signal.or_low:.2f} - ${signal.or_high:.2f}
Time: {signal.timestamp.strftime('%H:%M:%S')}
"""
        color = "#10b981" if signal.signal_type == "LONG" else "#ef4444"
        return f"""
<div style="font-family: Arial, sans-serif; max-width: 600px;">
  <h2 style="color: {color};">{signal.signal_type} SIGNAL - {signal.symbol}</h2>
  <div style="background: #f3f4f6; padding: 20px; border-radius: 8px;">
    <h3 style="margin: 0 0 15px 0;">ENTER NOW at ${entry}</h3>
    <p><strong>Stop Loss:</strong> ${stop}</p>
    <p><strong>Target:</strong> ${target}</p>
    <p><strong>Risk/Reward:</strong> 2:1</p>
    <hr>
    <p><strong>OR Range:</strong> ${signal.or_low:.2f} - ${signal.or_high:.2f}</p>
    <p><strong>Time:</strong> {signal.timestamp.strftime('%H:%M:%S')}</p>
  </div>
</div>
"""


# -----------------------------------------------------------------------------
# Market sessions / timezone status helpers
# -----------------------------------------------------------------------------
def _tz_now(tz_name: str) -> datetime:
    tz = pytz.timezone(tz_name)
    return datetime.now(tz)

def _combine_local(date_local: datetime, t: dtime, tz_name: str) -> datetime:
    tz = pytz.timezone(tz_name)
    naive = datetime(date_local.year, date_local.month, date_local.day, t.hour, t.minute, t.second)
    return tz.localize(naive)

def _format_td(delta: timedelta) -> str:
    secs = int(abs(delta.total_seconds()))
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s"

def _session_status(now: datetime, start: datetime, end: datetime) -> Dict[str, Any]:
    if start <= now < end:
        left = end - now
        return {"state": "open", "time_to": None, "time_left": _format_td(left)}
    if now < start:
        till = start - now
        return {"state": "closed", "time_to": _format_td(till), "time_left": None}
    # after end -> next day start
    nxt = start + timedelta(days=1)
    till = nxt - now
    return {"state": "closed", "time_to": _format_td(till), "time_left": None}

def get_global_market_status() -> Dict[str, Any]:
    """Return status for key trading sessions across timezones.
    Times are *local session times*; we treat Mon-Fri as active days for countdown display.
    """
    sessions = [
        # name, tz, start, end, note
        ("Tokyo", "Asia/Tokyo", dtime(9, 0), dtime(15, 0), "TSE cash"),
        ("Hong Kong", "Asia/Hong_Kong", dtime(9, 30), dtime(16, 0), "HKEX cash"),
        ("London", "Europe/London", dtime(8, 0), dtime(16, 30), "LSE cash"),
        ("Frankfurt", "Europe/Berlin", dtime(9, 0), dtime(17, 30), "Xetra"),
        ("New York", "America/New_York", dtime(9, 30), dtime(16, 0), "NYSE/Nasdaq"),
        ("Chicago", "America/Chicago", dtime(8, 30), dtime(15, 0), "CME RTH (indicative)"),
        ("Sydney", "Australia/Sydney", dtime(10, 0), dtime(16, 0), "ASX cash"),
    ]

    out = []
    for name, tz, st, en, note in sessions:
        now = _tz_now(tz)
        start = _combine_local(now, st, tz)
        end = _combine_local(now, en, tz)

        status = _session_status(now, start, end)
        out.append(
            {
                "name": name,
                "tz": tz,
                "local_time": now.strftime("%H:%M:%S"),
                "local_date": now.strftime("%Y-%m-%d"),
                "start": start.strftime("%H:%M"),
                "end": end.strftime("%H:%M"),
                "note": note,
                **status,
            }
        )

    any_open = any(s["state"] == "open" for s in out)
    return {"any_open": any_open, "sessions": out}


# -----------------------------------------------------------------------------
# Scanner
# -----------------------------------------------------------------------------
class FusedDashboardScanner(ORBScanner):
    """Scanner with: pro analytics + control + notifications."""

    def __init__(self, *args, notification_manager=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_update = datetime.now(self.timezone)
        self.notification_manager = notification_manager

        self.price_history: Dict[str, List[Dict[str, Any]]] = {symbol: [] for symbol in self.symbols}
        self.daily_stats = {
            "total_signals": 0,
            "long_signals": 0,
            "short_signals": 0,
            "symbols_with_or": 0,
        }
        self.stats_reset_date = datetime.now(self.timezone).date()

        # Defensive init: ensure per-symbol dicts exist for all configured symbols (prevents KeyError on reload/connect)
        for symbol in list(self.symbols):
            if symbol not in self.or_data:
                self.or_data[symbol] = {"high": None, "low": None, "mid": None, "captured": False}
            if symbol not in self.breakout_state:
                self.breakout_state[symbol] = {
                    "long_breakout_active": False,
                    "short_breakout_active": False,
                    "was_in_zone": True,
                    "last_check": None,
                }
            if symbol not in self.signals_today:
                self.signals_today[symbol] = []

    def update_symbols(self, new_symbols: List[str]):
        # Remove old symbols
        for symbol in list(self.symbols):
            if symbol not in new_symbols:
                self.or_data.pop(symbol, None)
                self.breakout_state.pop(symbol, None)
                self.signals_today.pop(symbol, None)
                self.price_history.pop(symbol, None)

        # Add new symbols
        for symbol in new_symbols:
            if symbol not in self.symbols:
                self.or_data[symbol] = {"high": None, "low": None, "mid": None, "captured": False}
                self.breakout_state[symbol] = {
                    "long_breakout_active": False,
                    "short_breakout_active": False,
                    "was_in_zone": True,
                    "last_check": None,
                }
                self.signals_today[symbol] = []
                self.price_history[symbol] = []

        self.symbols = new_symbols
        print(f"✅ Symbols updated: {len(new_symbols)} symbols now monitored")

    def get_current_prices(self) -> Dict[str, Optional[float]]:
        prices: Dict[str, Optional[float]] = {}
        for symbol in self.symbols:
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.history(period="1d", interval="1m")
                if not data.empty:
                    prices[symbol] = round(float(data["Close"].iloc[-1]), 2)
                else:
                    prices[symbol] = None
            except Exception:
                # Silently fail - don't spam logs for temporary failures
                prices[symbol] = None
        return prices

    def scan_all_symbols(self) -> List[ORBSignal]:
        # Check if we need to reset daily stats (new trading day)
        today = datetime.now(self.timezone).date()
        if today != self.stats_reset_date:
            print(f"📊 Resetting daily stats for new trading day: {today}")
            self.daily_stats = {
                "total_signals": 0,
                "long_signals": 0,
                "short_signals": 0,
                "symbols_with_or": 0,
            }
            self.stats_reset_date = today
        
        signals = super().scan_all_symbols()

        for signal in signals:
            self.daily_stats["total_signals"] += 1
            if signal.signal_type == "LONG":
                self.daily_stats["long_signals"] += 1
            else:
                self.daily_stats["short_signals"] += 1

            if self.notification_manager:
                self._send_signal_notifications(signal)

            socketio.emit(
                "new_signal",
                {
                    "symbol": signal.symbol,
                    "type": signal.signal_type,
                    "timestamp": signal.timestamp.isoformat(),
                    "current_price": round(signal.current_price, 2),
                    "or_high": round(signal.or_high, 2),
                    "or_mid": round(signal.or_mid, 2),
                    "or_low": round(signal.or_low, 2),
                    "range_size": round(signal.or_high - signal.or_low, 2),
                    "time_display": signal.timestamp.strftime("%H:%M:%S"),
                    "entry": round(signal.or_mid, 2),
                    "stop": round(signal.or_low if signal.signal_type == "LONG" else signal.or_high, 2),
                    "target": round(
                        signal.or_mid + (signal.or_mid - signal.or_low) * 2
                        if signal.signal_type == "LONG"
                        else signal.or_mid - (signal.or_high - signal.or_mid) * 2,
                        2,
                    ),
                },
            )

        # Update stats
        active_breakouts = 0
        symbols_with_or = 0
        active_symbols = 0
        for symbol in self.symbols:
            state = self.breakout_state.get(symbol) or {}
            or_info = self.or_data.get(symbol) or {}
            if state.get("long_breakout_active") or state.get("short_breakout_active"):
                active_breakouts += 1
                active_symbols += 1
            if or_info.get("captured"):
                symbols_with_or += 1
        self.daily_stats["active_breakouts"] = active_breakouts
        self.daily_stats["symbols_with_or"] = symbols_with_or

        self.last_update = datetime.now(self.timezone)
        socketio.emit("status_update", self.get_comprehensive_status())

        prices = self.get_current_prices()
        socketio.emit("price_update", prices)

        # Global market session status
        socketio.emit("market_sessions", get_global_market_status())

        return signals

    def _send_signal_notifications(self, signal: ORBSignal):
        if settings.get("telegram_enabled") and settings.get("telegram_bot_token") and settings.get("telegram_chat_id"):
            message = NotificationManager.format_signal_message(signal, "telegram")
            try:
                asyncio.run(
                    NotificationManager.send_telegram(
                        settings["telegram_bot_token"],
                        settings["telegram_chat_id"],
                        message,
                    )
                )
            except Exception as e:
                print(f"Telegram notification failed: {e}")

        if settings.get("email_enabled") and settings.get("email_sender") and settings.get("email_password"):
            subject = f"{signal.signal_type} Signal: {signal.symbol}"
            body = NotificationManager.format_signal_message(signal, "email")
            try:
                NotificationManager.send_email(
                    settings["email_smtp_server"],
                    int(settings["email_smtp_port"]),
                    settings["email_sender"],
                    settings["email_password"],
                    settings.get("email_recipient") or settings["email_sender"],
                    subject,
                    body,
                )
            except Exception as e:
                print(f"Email notification failed: {e}")

    def get_comprehensive_status(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {
            "last_update": self.last_update.isoformat(),
            "trading_hours": self.is_trading_hours(),
            "daily_stats": self.daily_stats,
            "symbols": {},
            "settings": settings,
            "active_symbols": active_symbols,
        }

        for symbol in self.symbols:
            or_info = self.or_data.get(symbol) or {}
            state = self.breakout_state.get(symbol) or {}

            or_range = (or_info["high"] - or_info["low"]) if or_info["high"] else None

            status["symbols"][symbol] = {
                "or_captured": bool(or_info["captured"]),
                "or_high": round(or_info["high"], 2) if or_info["high"] else None,
                "or_low": round(or_info["low"], 2) if or_info["low"] else None,
                "or_mid": round(or_info["mid"], 2) if or_info["mid"] else None,
                "or_range": round(or_range, 2) if or_range is not None else None,
                "long_breakout_active": bool(state["long_breakout_active"]),
                "short_breakout_active": bool(state["short_breakout_active"]),
                "signals_count": len(self.signals_today.get(symbol, [])),
                "signals": [
                    {
                        "type": s.signal_type,
                        "timestamp": s.timestamp.isoformat(),
                        "time_display": s.timestamp.strftime("%H:%M:%S"),
                        "price": round(s.current_price, 2),
                        "entry": round(s.or_mid, 2),
                        "stop": round(s.or_low if s.signal_type == "LONG" else s.or_high, 2),
                        "target": round(
                            s.or_mid + (s.or_mid - s.or_low) * 2
                            if s.signal_type == "LONG"
                            else s.or_mid - (s.or_high - s.or_mid) * 2,
                            2,
                        ),
                    }
                    for s in self.signals_today.get(symbol, [])
                ],
            }

        return status


# -----------------------------------------------------------------------------
# Background task
# -----------------------------------------------------------------------------
def scanner_background_task():
    global scanner
    print("📡 Scanner background task started")

    while True:
        try:
            if scanner:
                if scanner.is_trading_hours():
                    scanner.scan_all_symbols()
                else:
                    socketio.emit(
                        "heartbeat",
                        {"status": "offline", "message": "Market closed", "time": datetime.now().isoformat()},
                    )
                    # still emit sessions even off-hours
                    socketio.emit("market_sessions", get_global_market_status())
            time.sleep(int(scanner.check_interval) if scanner else 60)
        except Exception as e:
            print(f"❌ Error in scanner task: {e}")
            socketio.emit("error", {"message": str(e)})
            time.sleep(60)


# -----------------------------------------------------------------------------
# API routes
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("dashboard_fused.html")

@app.route("/api/status")
def api_status():
    if scanner:
        return jsonify(scanner.get_comprehensive_status())
    return jsonify({"error": "Scanner not initialized"}), 400

@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    global settings, scanner
    if request.method == "POST":
        data = request.json or {}
        settings.update(data)

        if scanner and "breakout_distance" in data:
            scanner.breakout_distance = float(data["breakout_distance"])
        if scanner and "check_interval" in data:
            scanner.check_interval = int(data["check_interval"])

        socketio.emit("settings_updated", settings)
        return jsonify({"success": True, "settings": settings})
    return jsonify(settings)

@app.route("/api/symbols", methods=["GET", "POST", "DELETE"])
def api_symbols():
    global active_symbols, scanner

    if request.method == "GET":
        return jsonify({"symbols": active_symbols})

    data = request.json or {}
    symbol = (data.get("symbol") or "").upper().strip()
    if not symbol:
        return jsonify({"error": "Symbol required"}), 400

    if request.method == "POST":
        if symbol in active_symbols:
            return jsonify({"error": "Symbol already exists"}), 400
        
        # Reject invalid symbol formats (futures, indices with !, etc.)
        if not symbol or len(symbol) > 10 or any(c in symbol for c in ['!', '=']):
            return jsonify({"error": "Invalid symbol format. Use regular stock/ETF tickers only (no futures/indices)."}), 400
        
        try:
            t = yf.Ticker(symbol)
            # Try to fetch recent data to validate symbol exists
            hist = t.history(period="5d", interval="1d")
            if hist is None or hist.empty:
                return jsonify({"error": f"Symbol {symbol} not found or no data available"}), 400
            
            # Verify we can get current intraday data
            current_data = t.history(period="1d", interval="1m")
            if current_data is None or current_data.empty:
                return jsonify({"error": f"Symbol {symbol} exists but has no intraday data available"}), 400
                
        except Exception as e:
            return jsonify({"error": f"Symbol validation failed: {str(e)}"}), 400

        active_symbols.append(symbol)
        if scanner:
            scanner.update_symbols(active_symbols)
        persist_config({"settings": settings, "active_symbols": active_symbols})
        socketio.emit("symbols_updated", {"symbols": active_symbols})
        try:
            if scanner:
                socketio.emit("status_update", scanner.get_comprehensive_status())
        except Exception as e:
            print(f"⚠️ Failed to emit status_update after adding symbol: {e}")
        return jsonify({"success": True, "symbols": active_symbols})

    # DELETE
    if symbol not in active_symbols:
        return jsonify({"error": "Symbol not found"}), 404
    active_symbols.remove(symbol)
    if scanner:
        scanner.update_symbols(active_symbols)
    persist_config({"settings": settings, "active_symbols": active_symbols})
    socketio.emit("symbols_updated", {"symbols": active_symbols})
    try:
        socketio.emit("status_update", scanner.get_comprehensive_status() if scanner else {})
    except Exception:
        pass
    return jsonify({"success": True, "symbols": active_symbols})

@app.route("/api/test-telegram", methods=["POST"])
def api_test_telegram():
    data = request.json or {}
    token = data.get("token", "")
    chat_id = data.get("chat_id", "")
    if not token or not chat_id:
        return jsonify({"error": "Token and chat_id required"}), 400
    message = "🟢 <b>Test Message</b>\n\nTelegram notifications are working!"
    try:
        ok = asyncio.run(NotificationManager.send_telegram(token, chat_id, message))
        return jsonify({"success": bool(ok), "message": "Test message sent!" if ok else "Failed to send message"}), (200 if ok else 500)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/test-email", methods=["POST"])
def api_test_email():
    data = request.json or {}
    required = ["smtp_server", "smtp_port", "sender", "password", "recipient"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} required"}), 400

    subject = "ORB Scanner Test"
    body = """
<div style="font-family: Arial, sans-serif;">
  <h2 style="color: #10b981;">✅ Test Message</h2>
  <p>Email notifications are working!</p>
</div>
"""
    try:
        ok = NotificationManager.send_email(
            data["smtp_server"],
            int(data["smtp_port"]),
            data["sender"],
            data["password"],
            data["recipient"],
            subject,
            body,
        )
        return jsonify({"success": bool(ok), "message": "Test email sent!" if ok else "Failed to send email"}), (200 if ok else 500)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/start")
def api_start():
    global scanner, scanner_thread
    if scanner is None:
        scanner = FusedDashboardScanner(
            symbols=active_symbols,
            breakout_distance=float(settings["breakout_distance"]),
            timezone="America/New_York",
            check_interval=int(settings["check_interval"]),
            notification_manager=NotificationManager(),
        )
        scanner_thread = Thread(target=scanner_background_task, daemon=True)
        scanner_thread.start()
        return jsonify({"status": "started", "symbols": len(active_symbols)})
    return jsonify({"status": "already_running"})

@app.route("/api/restart")
def api_restart():
    global scanner
    if scanner:
        scanner.update_symbols(active_symbols)
        return jsonify({"status": "restarted", "symbols": len(active_symbols)})
    return api_start()

@app.route("/api/prices/<symbol>")
def api_symbol_prices(symbol: str):
    symbol = symbol.upper().strip()
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1d", interval="1m")
        if df is None or df.empty:
            return jsonify({"error": "No data"}), 404
        return jsonify(
            {
                "timestamps": [ts.isoformat() for ts in df.index],
                "prices": [float(x) for x in df["Close"].tolist()],
                "volumes": [int(x) for x in df["Volume"].fillna(0).tolist()],
                "highs": [float(x) for x in df["High"].tolist()],
                "lows": [float(x) for x in df["Low"].tolist()],
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/symbol/<symbol>/stats")
def api_symbol_stats(symbol: str):
    symbol = symbol.upper().strip()
    try:
        t = yf.Ticker(symbol)
        info = getattr(t, "info", {}) or {}
        # Keep it small & stable for the UI
        keys = [
            "shortName", "longName", "symbol", "quoteType", "currency", "exchange",
            "regularMarketPrice", "regularMarketChange", "regularMarketChangePercent",
            "regularMarketDayHigh", "regularMarketDayLow",
            "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
            "marketCap", "trailingPE", "forwardPE", "dividendYield", "beta",
            "averageVolume", "averageVolume10days",
        ]
        filtered = {k: info.get(k) for k in keys if k in info}
        return jsonify({"symbol": symbol, "info": filtered})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------------------------------------------------------
# Socket events
# -----------------------------------------------------------------------------
@socketio.on("connect")
def on_connect(auth=None):
    print(f"✅ Client connected: {request.sid}")
    emit("symbols_updated", {"symbols": active_symbols})
    emit("settings_update", {"settings": settings})
    if scanner:
        try:
            status = scanner.get_comprehensive_status()
            emit("status_update", status)
        except Exception as e:
            print(f"⚠️ status_update failed on connect: {e}")
            # Send minimal status to avoid blocking UI
            emit("status_update", {
                "daily_stats": scanner.daily_stats if hasattr(scanner, 'daily_stats') else {},
                "symbols": {},
                "error": str(e)
            })
        try:
            emit("market_sessions", get_global_market_status())
        except Exception as e:
            print(f"⚠️ market_sessions failed: {e}")
        emit("connected", {"message": "Connected to ORB Scanner"})

@socketio.on("disconnect")
def on_disconnect():
    print(f"❌ Client disconnected: {request.sid}")


# -----------------------------------------------------------------------------
# HTML template generator (Pro style + Control features)
# -----------------------------------------------------------------------------
def create_fused_dashboard_html() -> str:
    # Keep it as a single-file template for easy running.
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ORB Scanner - Fused Dashboard</title>
  <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    :root {
      --bg-primary: #0f172a;
      --bg-secondary: #1e293b;
      --bg-tertiary: #334155;
      --text-primary: #f1f5f9;
      --text-secondary: #cbd5e1;
      --accent-green: #10b981;
      --accent-red: #ef4444;
      --accent-blue: #3b82f6;
      --accent-yellow: #f59e0b;
      --border: #475569;
      --shadow: rgba(0, 0, 0, 0.3);
    }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: linear-gradient(135deg, var(--bg-primary) 0%, #1a1f2e 100%);
      color: var(--text-primary);
      min-height: 100vh;
      overflow-x: hidden;
    }
    .header {
      background: var(--bg-secondary);
      padding: 1.25rem 2rem;
      box-shadow: 0 4px 6px var(--shadow);
      position: sticky;
      top: 0;
      z-index: 100;
      border-bottom: 2px solid var(--border);
    }
    .header-content {
      max-width: 1600px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1.5rem;
    }
    .logo { display:flex; align-items:center; gap: 1rem; }
    .logo i { font-size: 2rem; color: var(--accent-blue); }
    .logo h1 { font-size: 1.35rem; font-weight: 800; }
    .logo .sub { font-size: .75rem; color: var(--text-secondary); }

    .header-stats { display:flex; gap: 1.75rem; }
    .stat-item { text-align:center; min-width: 90px; }
    .stat-label { font-size: .72rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: .06em; }
    .stat-value { font-size: 1.45rem; font-weight: 800; margin-top: .25rem; }
    .stat-value.green { color: var(--accent-green); }
    .stat-value.red { color: var(--accent-red); }
    .stat-value.blue { color: var(--accent-blue); }

    .connection-status {
      display:flex; align-items:center; gap: .5rem;
      padding: .5rem 1rem; background: var(--bg-tertiary); border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.06);
      white-space: nowrap;
    }
    .status-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--accent-green); animation: pulse 2s infinite; }
    @keyframes pulse { 0%,100% {opacity:1;} 50% {opacity:.5;} }

    .container { max-width: 1600px; margin: 0 auto; padding: 2rem; }
    .dashboard-grid {
      display:grid; grid-template-columns: 1.25fr 1fr 1fr;
      gap: 1.25rem; margin-bottom: 1.5rem;
    }
    .card {
      background: var(--bg-secondary);
      border-radius: 14px;
      padding: 1.25rem;
      box-shadow: 0 4px 6px var(--shadow);
      border: 1px solid var(--border);
    }
    .card-header {
      display:flex; justify-content: space-between; align-items:center;
      margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border);
      gap: 1rem;
    }
    .card-title { font-size: 1.05rem; font-weight: 700; display:flex; align-items:center; gap:.5rem; }
    .muted { color: var(--text-secondary); font-size: .875rem; }
    .signals-feed { grid-column: 1 / -1; }

    .signal-item {
      background: var(--bg-tertiary);
      padding: 1rem;
      border-radius: 10px;
      margin-bottom: .9rem;
      border-left: 4px solid var(--accent-blue);
      animation: slideIn .25s ease-out;
    }
    .signal-item.long { border-left-color: var(--accent-green); }
    .signal-item.short { border-left-color: var(--accent-red); }
    @keyframes slideIn { from {opacity:0; transform: translateX(-14px);} to {opacity:1; transform:none;} }

    .signal-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: .35rem; }
    .signal-symbol { font-size: 1.15rem; font-weight: 800; }
    .signal-type {
      padding: .25rem .7rem;
      border-radius: 999px;
      font-size: .72rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .05em;
    }
    .signal-type.long { background: var(--accent-green); color: white; }
    .signal-type.short { background: var(--accent-red); color: white; }
    .signal-details { display:grid; grid-template-columns: repeat(4, 1fr); gap: .75rem; margin-top: .8rem; }
    .signal-detail { text-align:center; }
    .signal-detail-label { font-size: .72rem; color: var(--text-secondary); margin-bottom: .2rem; }
    .signal-detail-value { font-size: 1.05rem; font-weight: 800; }

    .symbols-grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; }
    .symbol-card {
      background: var(--bg-tertiary);
      padding: 1rem;
      border-radius: 12px;
      cursor:pointer;
      transition: transform .15s, border-color .15s, box-shadow .15s;
      border: 2px solid transparent;
    }
    .symbol-card:hover { transform: translateY(-2px); border-color: var(--accent-blue); box-shadow: 0 10px 18px rgba(0,0,0,0.25); }
    .symbol-card.active { border-color: var(--accent-green); background: rgba(16,185,129,0.08); }
    .symbol-card-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: .75rem; gap: .75rem; }
    .symbol-name { font-size: 1.1rem; font-weight: 800; }
    .symbol-price { font-size: 1rem; color: var(--accent-blue); font-weight: 700; }
    .symbol-or { font-size: .86rem; color: var(--text-secondary); margin-bottom: .55rem; }
    .symbol-status { display:inline-block; padding: .25rem .7rem; border-radius: 999px; font-size: .72rem; font-weight: 700; }
    .symbol-status.watching { background: rgba(59,130,246,0.18); color: var(--accent-blue); }
    .symbol-status.breakout { background: rgba(245,158,11,0.18); color: var(--accent-yellow); }

    .settings-panel { background: var(--bg-tertiary); padding: 1.15rem; border-radius: 12px; }
    .setting-item { margin-bottom: 1rem; }
    .setting-label { display:block; font-size:.83rem; font-weight:700; margin-bottom:.45rem; color: var(--text-secondary); }
    .setting-input {
      width: 100%; padding: .65rem .7rem;
      background: var(--bg-primary);
      border: 1px solid var(--border);
      border-radius: 10px;
      color: var(--text-primary);
      font-size: 1rem;
    }
    .setting-input:focus { outline:none; border-color: var(--accent-blue); }
    .btn { padding: .75rem 1rem; border:none; border-radius: 10px; font-weight:800; cursor:pointer; transition: transform .05s, filter .15s; }
    .btn:active { transform: translateY(1px); }
    .btn-primary { background: var(--accent-blue); color:white; }
    .btn-primary:hover { filter: brightness(1.05); }
    .btn-success { background: var(--accent-green); color:white; }
    .btn-danger { background: var(--accent-red); color:white; }
    .btn-ghost { background: transparent; color: var(--text-primary); border: 1px solid rgba(255,255,255,0.12); }
    .btn-row { display:flex; gap: .75rem; flex-wrap: wrap; }

    .toggle-switch { position: relative; width: 52px; height: 28px; display:inline-block; }
    .toggle-switch input { opacity:0; width:0; height:0; }
    .toggle-slider { position:absolute; cursor:pointer; inset:0; background-color: var(--border); transition:.25s; border-radius: 999px; }
    .toggle-slider:before { position:absolute; content:""; height: 20px; width: 20px; left: 4px; bottom: 4px; background-color: white; transition:.25s; border-radius: 50%; }
    input:checked + .toggle-slider { background-color: var(--accent-green); }
    input:checked + .toggle-slider:before { transform: translateX(24px); }

    .market-big { text-align:center; padding: 1rem 0 0.25rem; }
    .market-clock { font-size: 2.25rem; font-weight: 900; letter-spacing: .03em; }
    .market-status { font-size: 1.05rem; margin-top: .35rem; font-weight: 800; }
    .market-sessions { display:flex; flex-direction: column; gap:.6rem; margin-top: 1rem; }
    .session-row {
      display:flex; justify-content: space-between; align-items: center; gap: .75rem;
      padding: .75rem; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06);
      border-radius: 12px;
    }
    .session-left { display:flex; flex-direction: column; gap: .15rem; }
    .session-name { font-weight: 900; }
    .session-meta { font-size: .78rem; color: var(--text-secondary); }
    .pill {
      display:inline-flex; align-items:center; gap:.4rem;
      padding: .25rem .65rem; border-radius: 999px; font-size: .75rem; font-weight: 800;
      border: 1px solid rgba(255,255,255,0.12);
      white-space: nowrap;
    }
    .pill.open { background: rgba(16,185,129,0.16); color: var(--accent-green); }
    .pill.closed { background: rgba(239,68,68,0.14); color: var(--accent-red); }

    .chart-container { position: relative; height: 300px; margin-top: .5rem; }
    .empty-state { text-align:center; padding: 2.25rem; color: var(--text-secondary); }
    .empty-state i { font-size: 2.5rem; margin-bottom: 1rem; opacity: .3; }

    .split { display:grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
    .hr { height:1px; background: rgba(255,255,255,0.08); margin: 1rem 0; }

    /* Modal */
    .modal-backdrop {
      position: fixed; inset: 0; background: rgba(0,0,0,0.65);
      display:none; align-items: center; justify-content: center;
      padding: 1.5rem;
      z-index: 1000;
    }
    .modal {
      width: min(980px, 100%);
      background: var(--bg-secondary);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 20px 50px rgba(0,0,0,0.55);
      overflow: hidden;
    }
    .modal-header { display:flex; justify-content: space-between; align-items: center; padding: 1rem 1.25rem; border-bottom: 1px solid var(--border); }
    .modal-title { font-size: 1.1rem; font-weight: 900; display:flex; align-items: center; gap: .65rem; }
    .modal-body { padding: 1.25rem; }
    .kv { display:grid; grid-template-columns: repeat(3, 1fr); gap: .75rem; }
    .kv .item { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: .75rem; }
    .kv .k { font-size: .72rem; color: var(--text-secondary); margin-bottom: .2rem; text-transform: uppercase; letter-spacing: .05em; }
    .kv .v { font-size: 1.05rem; font-weight: 900; }
    .modal-actions { display:flex; justify-content: flex-end; gap: .75rem; padding: 0 1.25rem 1.25rem; }

    @media (max-width: 1200px) { .dashboard-grid { grid-template-columns: 1fr 1fr; } }
    @media (max-width: 900px) { .dashboard-grid { grid-template-columns: 1fr; } .header-stats { display:none; } .kv { grid-template-columns: 1fr 1fr; } }
    @media (max-width: 560px) { .signal-details { grid-template-columns: 1fr 1fr; } .kv { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="header">
    <div class="header-content">
      <div class="logo">
        <i class="fas fa-chart-line"></i>
        <div>
          <h1>ORB Scanner</h1>
          <div class="sub">Pro style + Control features</div>
        </div>
      </div>

      <div class="header-stats">
        <div class="stat-item"><div class="stat-label">Total Signals</div><div class="stat-value blue" id="total-signals">0</div></div>
        <div class="stat-item"><div class="stat-label">Long</div><div class="stat-value green" id="long-signals">0</div></div>
        <div class="stat-item"><div class="stat-label">Short</div><div class="stat-value red" id="short-signals">0</div></div>
</div>

      <div class="connection-status">
        <div class="status-dot" id="conn-dot"></div>
        <span id="connection-text">Connected</span>
      </div>
    </div>
  </div>

  <div class="container">
    <div class="dashboard-grid">
      <!-- Signals Feed -->
      <div class="card signals-feed">
        <div class="card-header">
          <div class="card-title"><i class="fas fa-bell"></i> Recent Signals</div>
          <div class="muted" id="last-update">Last update: --:--:--</div>
        </div>
        <div id="signals-container">
          <div class="empty-state">
            <i class="fas fa-chart-area"></i>
            <div>Waiting for signals...</div>
            <div style="font-size: .9rem; margin-top: .5rem;">Signals will appear here when ORB breakouts occur</div>
          </div>
        </div>
      </div>

      <!-- Settings -->
      <div class="card">
        <div class="card-header">
          <div class="card-title"><i class="fas fa-cog"></i> Settings</div>
        </div>
        <div class="settings-panel">
          <div class="setting-item">
            <label class="setting-label">Breakout Distance (points)</label>
            <input type="number" class="setting-input" id="breakout-distance" value="2.0" step="0.5" min="0.5" max="10">
          </div>
          <div class="setting-item">
            <label class="setting-label">Check Interval (seconds)</label>
            <input type="number" class="setting-input" id="check-interval" value="60" step="15" min="15" max="300">
          </div>

          <div class="split">
            <div class="setting-item">
              <label class="setting-label" style="display:flex; justify-content: space-between; align-items: center;">
                Sound Alerts
                <label class="toggle-switch">
                  <input type="checkbox" id="sound-alerts" checked>
                  <span class="toggle-slider"></span>
                </label>
              </label>
            </div>
            <div class="setting-item">
              <label class="setting-label" style="display:flex; justify-content: space-between; align-items: center;">
                Desktop Notifications
                <label class="toggle-switch">
                  <input type="checkbox" id="desktop-notifications" checked>
                  <span class="toggle-slider"></span>
                </label>
              </label>
            </div>
          </div>

          <button class="btn btn-primary" style="width:100%;" onclick="saveSettings()">
            <i class="fas fa-save"></i> Save Settings
          </button>

          <div class="hr"></div>

          <!-- Symbol management -->
          <div class="setting-item">
            <label class="setting-label">Add Symbol</label>
            <div class="btn-row">
              <input type="text" class="setting-input" id="new-symbol" placeholder="e.g. AAPL" style="flex: 1; min-width: 180px;">
              <button class="btn btn-success" onclick="addSymbol()"><i class="fas fa-plus"></i> Add</button>
            </div>
            <div class="muted" style="margin-top:.5rem;">Click a symbol card below to open details.</div>
          </div>

          <div class="hr"></div>

          <!-- Telegram -->
          <div class="setting-item">
            <label class="setting-label" style="display:flex; justify-content: space-between; align-items:center;">
              Telegram Notifications
              <label class="toggle-switch">
                <input type="checkbox" id="telegram-enabled" onchange="saveSettings(true)">
                <span class="toggle-slider"></span>
              </label>
            </label>
            <input type="text" class="setting-input" id="telegram-token" placeholder="Bot token" style="margin-top:.5rem;">
            <input type="text" class="setting-input" id="telegram-chat-id" placeholder="Chat ID" style="margin-top:.5rem;">
            <div class="btn-row" style="margin-top:.6rem;">
              <button class="btn btn-ghost" onclick="testTelegram()"><i class="fas fa-paper-plane"></i> Test</button>
              <div class="muted" id="telegram-status"></div>
            </div>
          </div>

          <!-- Email -->
          <div class="setting-item">
            <label class="setting-label" style="display:flex; justify-content: space-between; align-items:center;">
              Email Notifications
              <label class="toggle-switch">
                <input type="checkbox" id="email-enabled" onchange="saveSettings(true)">
                <span class="toggle-slider"></span>
              </label>
            </label>
            <input type="text" class="setting-input" id="email-smtp" value="smtp.gmail.com" placeholder="SMTP server" style="margin-top:.5rem;">
            <input type="number" class="setting-input" id="email-port" value="587" placeholder="SMTP port" style="margin-top:.5rem;">
            <input type="email" class="setting-input" id="email-sender" placeholder="Sender email" style="margin-top:.5rem;">
            <input type="password" class="setting-input" id="email-password" placeholder="App password" style="margin-top:.5rem;">
            <input type="email" class="setting-input" id="email-recipient" placeholder="Recipient email (optional)" style="margin-top:.5rem;">
            <div class="btn-row" style="margin-top:.6rem;">
              <button class="btn btn-ghost" onclick="testEmail()"><i class="fas fa-paper-plane"></i> Test</button>
              <div class="muted" id="email-status"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Market Status (multi sessions) -->
      <div class="card">
        <div class="card-header">
          <div class="card-title"><i class="fas fa-clock"></i> Market Status</div>
        </div>

        <div class="market-big">
          <div class="market-clock" id="market-clock">--:--:--</div>
          <div class="market-status" id="market-status">--</div>
        </div>

        <div class="market-sessions" id="market-sessions">
          <div class="empty-state" style="padding: 1.5rem;">
            <i class="fas fa-spinner fa-spin"></i>
            <div>Loading sessions...</div>
          </div>
        </div>
      </div>

      <!-- Activity Chart -->
      <div class="card">
        <div class="card-header">
          <div class="card-title"><i class="fas fa-chart-bar"></i> Today's Activity</div>
        </div>
        <div class="chart-container">
          <canvas id="activityChart"></canvas>
        </div>
      </div>
    </div>

    <!-- Symbols Grid -->
    <div class="card">
      <div class="card-header">
        <div class="card-title"><i class="fas fa-list"></i> Monitored Symbols</div>
        <div class="muted" id="symbols-hint">Tip: click any symbol card for details</div>
      </div>
      <div class="symbols-grid" id="symbols-grid">
        <div class="empty-state">
          <i class="fas fa-spinner fa-spin"></i>
          <div>Loading symbols...</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Symbol modal -->
  <div class="modal-backdrop" id="modal-backdrop" onclick="closeModal(event)">
    <div class="modal" onclick="event.stopPropagation()">
      <div class="modal-header">
        <div class="modal-title">
          <i class="fas fa-chart-line"></i>
          <span id="modal-title">SYMBOL</span>
        </div>
        <div class="btn-row">
          <button class="btn btn-danger" onclick="removeCurrentSymbol()"><i class="fas fa-trash"></i> Remove</button>
          <button class="btn btn-ghost" onclick="closeModal()"><i class="fas fa-xmark"></i></button>
        </div>
      </div>
      <div class="modal-body">
        <div class="kv" id="modal-kv"></div>
        <div class="hr"></div>
        <div class="card" style="padding: 1rem; border-radius: 12px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);">
          <div style="display:flex; justify-content: space-between; align-items:center; gap: 1rem;">
            <div style="font-weight: 900;">Intraday (1m)</div>
            <div class="muted" id="modal-chart-status">Loading...</div>
          </div>
          <div class="chart-container" style="height: 220px;">
            <canvas id="symbolChart"></canvas>
          </div>
        </div>

        <div class="hr"></div>

        <div class="card" style="padding: 1rem; border-radius: 12px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);">
          <div style="font-weight: 900; margin-bottom: .5rem;">Signals Today</div>
          <div id="modal-signals" class="muted">--</div>
        </div>
      </div>
      <div class="modal-actions">
        <button class="btn btn-primary" onclick="refreshModal()"><i class="fas fa-rotate"></i> Refresh</button>
        <button class="btn btn-ghost" onclick="closeModal()">Close</button>
      </div>
    </div>
  </div>

  <script>
    const socket = io();

    let allSignals = [];
    let symbolsData = {};
    let settings = {};
    let activityChart = null;

    let sessionsData = null;

    let currentPrices = {};
    let currentModalSymbol = null;
    let symbolChart = null;

    // Init
    document.addEventListener('DOMContentLoaded', () => {
      initializeActivityChart();
      requestNotificationPermission();
      startEtClock();

      // Start scanner
      fetch('/api/start').then(r => r.json()).then(() => {});
    });

    // Socket handlers
    socket.on('connect', () => {
      document.getElementById('connection-text').textContent = 'Connected';
      document.getElementById('conn-dot').style.background = 'var(--accent-green)';
    });

    socket.on('disconnect', () => {
      document.getElementById('connection-text').textContent = 'Disconnected';
      document.getElementById('conn-dot').style.background = 'var(--accent-red)';
    });

    socket.on('new_signal', (signal) => {
      allSignals.unshift(signal);

      if (settings.sound_alerts) playAlertSound();
      if (settings.desktop_notifications && Notification.permission === 'granted') {
        new Notification(`${signal.type} Signal: ${signal.symbol}`, {
          body: `Entry: $${signal.entry} | Stop: $${signal.stop} | Target: $${signal.target}`
        });
      }

      updateSignalsDisplay();
      updateActivityChart();
      // If modal open for this symbol, refresh signals section
      if (currentModalSymbol && currentModalSymbol === signal.symbol) {
        refreshModalSignals();
      }
    });

    socket.on('status_update', (status) => {
      const stats = status.daily_stats || {};
      document.getElementById('total-signals').textContent = stats.total_signals ?? 0;
      document.getElementById('long-signals').textContent = stats.long_signals ?? 0;
      document.getElementById('short-signals').textContent = stats.short_signals ?? 0;
      const updateTime = new Date(status.last_update);
      document.getElementById('last-update').textContent = `Last update: ${updateTime.toLocaleTimeString()}`;

      symbolsData = status.symbols || {};
      settings = status.settings || settings;

      hydrateSettingsPanel(settings);
      updateSymbolsDisplay();
    });

    socket.on('price_update', (prices) => {
      currentPrices = prices || {};
      Object.entries(currentPrices).forEach(([symbol, price]) => {
        const el = document.querySelector(`[data-symbol="${symbol}"] .symbol-price`);
        if (el) el.textContent = price ? `$${price}` : '--';
      });

      if (currentModalSymbol && currentPrices[currentModalSymbol]) {
        // soft update one field in modal if present
        const v = document.querySelector('[data-k="regularMarketPrice"] .v');
        if (v) v.textContent = `$${currentPrices[currentModalSymbol]}`;
      }
    });

    socket.on('market_sessions', (payload) => {
      sessionsData = payload;
      renderSessions(payload);
    });

    // UI render
    function updateSignalsDisplay() {
      const container = document.getElementById('signals-container');
      if (allSignals.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <i class="fas fa-chart-area"></i>
            <div>No signals yet today</div>
          </div>`;
        return;
      }

      container.innerHTML = allSignals.slice(0, 25).map(signal => `
        <div class="signal-item ${signal.type.toLowerCase()}">
          <div class="signal-header">
            <div class="signal-symbol">${signal.symbol}</div>
            <div class="signal-type ${signal.type.toLowerCase()}">${signal.type}</div>
          </div>
          <div class="muted">${signal.time_display}</div>
          <div class="signal-details">
            <div class="signal-detail"><div class="signal-detail-label">Entry</div><div class="signal-detail-value">$${signal.entry}</div></div>
            <div class="signal-detail"><div class="signal-detail-label">Stop</div><div class="signal-detail-value">$${signal.stop}</div></div>
            <div class="signal-detail"><div class="signal-detail-label">Target</div><div class="signal-detail-value">$${signal.target}</div></div>
            <div class="signal-detail"><div class="signal-detail-label">Range</div><div class="signal-detail-value">$${signal.range_size}</div></div>
          </div>
        </div>
      `).join('');
    }

    function updateSymbolsDisplay() {
      const container = document.getElementById('symbols-grid');

      const entries = Object.entries(symbolsData || {});
      if (entries.length === 0) return;

      container.innerHTML = entries.map(([symbol, data]) => {
        let statusText = 'Watching';
        let statusClass = 'watching';
        let cardClass = '';

        if (data.long_breakout_active) { statusText = 'LONG Breakout'; statusClass = 'breakout'; cardClass = 'active'; }
        else if (data.short_breakout_active) { statusText = 'SHORT Breakout'; statusClass = 'breakout'; cardClass = 'active'; }

        const orText = data.or_captured ? `OR: $${data.or_low} - $${data.or_high}` : 'Waiting for OR...';

        return `
          <div class="symbol-card ${cardClass}" data-symbol="${symbol}" onclick="openSymbolModal('${symbol}')">
            <div class="symbol-card-header">
              <div class="symbol-name">${symbol}</div>
              <div class="symbol-price">${currentPrices[symbol] ? `$${currentPrices[symbol]}` : '--'}</div>
            </div>
            <div class="symbol-or">${orText}</div>
            <div class="symbol-status ${statusClass}">${statusText}</div>
            ${data.signals_count > 0 ? `<div style="margin-top:.5rem; font-size:.75rem; color: var(--accent-green); font-weight:800;">${data.signals_count} signal(s)</div>` : ''}
          </div>
        `;
      }).join('');
    }

    function hydrateSettingsPanel(s) {
      if (!s) return;
      // Only hydrate once unless values differ; keep it simple.
      document.getElementById('breakout-distance').value = s.breakout_distance ?? 2.0;
      document.getElementById('check-interval').value = s.check_interval ?? 60;
      document.getElementById('sound-alerts').checked = !!s.sound_alerts;
      document.getElementById('desktop-notifications').checked = !!s.desktop_notifications;

      document.getElementById('telegram-enabled').checked = !!s.telegram_enabled;
      document.getElementById('telegram-token').value = s.telegram_bot_token ?? '';
      document.getElementById('telegram-chat-id').value = s.telegram_chat_id ?? '';

      document.getElementById('email-enabled').checked = !!s.email_enabled;
      document.getElementById('email-smtp').value = s.email_smtp_server ?? 'smtp.gmail.com';
      document.getElementById('email-port').value = s.email_smtp_port ?? 587;
      document.getElementById('email-sender').value = s.email_sender ?? '';
      document.getElementById('email-password').value = s.email_password ?? '';
      document.getElementById('email-recipient').value = s.email_recipient ?? '';
    }

    function renderSessions(payload) {
      const box = document.getElementById('market-sessions');
      if (!payload || !payload.sessions) return;
      const anyOpen = !!payload.any_open;

      // Use NY time for the big clock (keeps vibe consistent with ORB/US markets)
      const now = new Date();
      const etTime = new Date(now.toLocaleString("en-US", {timeZone: "America/New_York"}));
      document.getElementById('market-clock').textContent = etTime.toLocaleTimeString();
      document.getElementById('market-status').textContent = anyOpen ? 'At least one major session is OPEN' : 'All tracked sessions are CLOSED';
      document.getElementById('market-status').style.color = anyOpen ? 'var(--accent-green)' : 'var(--accent-red)';

      box.innerHTML = payload.sessions.map(s => {
        const isOpen = s.state === 'open';
        const right = isOpen ? `Closes in <b>${s.time_left}</b>` : `Opens in <b>${s.time_to}</b>`;
        return `
          <div class="session-row">
            <div class="session-left">
              <div class="session-name">${s.name}</div>
              <div class="session-meta">${s.note} • ${s.local_date} ${s.local_time} • ${s.start}-${s.end}</div>
            </div>
            <div class="pill ${isOpen ? 'open' : 'closed'}">
              <i class="fas ${isOpen ? 'fa-play' : 'fa-pause'}"></i>
              ${isOpen ? 'OPEN' : 'CLOSED'} · ${right}
            </div>
          </div>
        `;
      }).join('');
    }

    // Charts
    function initializeActivityChart() {
      const ctx = document.getElementById('activityChart');
      activityChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['Long', 'Short'],
          datasets: [{ label: 'Signals', data: [0, 0] }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, ticks: { stepSize: 1, color: '#cbd5e1' }, grid: { color: '#475569' } },
            x: { ticks: { color: '#cbd5e1' }, grid: { display: false } }
          }
        }
      });
    }

    function updateActivityChart() {
      const longSignals = allSignals.filter(s => s.type === 'LONG').length;
      const shortSignals = allSignals.filter(s => s.type === 'SHORT').length;
      if (activityChart) {
        activityChart.data.datasets[0].data = [longSignals, shortSignals];
        activityChart.update();
      }
    }

    // Market clock tick
    function startEtClock() {
      setInterval(() => {
        // Keep big clock alive even if websocket is quiet
        if (sessionsData) renderSessions(sessionsData);
      }, 1000);
    }

    // Settings + symbol actions
    async function saveSettings(silent=false) {
      const newSettings = {
        breakout_distance: parseFloat(document.getElementById('breakout-distance').value),
        check_interval: parseInt(document.getElementById('check-interval').value),
        sound_alerts: document.getElementById('sound-alerts').checked,
        desktop_notifications: document.getElementById('desktop-notifications').checked,

        telegram_enabled: document.getElementById('telegram-enabled').checked,
        telegram_bot_token: document.getElementById('telegram-token').value,
        telegram_chat_id: document.getElementById('telegram-chat-id').value,

        email_enabled: document.getElementById('email-enabled').checked,
        email_smtp_server: document.getElementById('email-smtp').value,
        email_smtp_port: parseInt(document.getElementById('email-port').value),
        email_sender: document.getElementById('email-sender').value,
        email_password: document.getElementById('email-password').value,
        email_recipient: document.getElementById('email-recipient').value
      };

      const r = await fetch('/api/settings', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(newSettings) });
      const data = await r.json().catch(() => ({}));
      if (!silent) alert(data.success ? 'Settings saved!' : (data.error || 'Failed to save settings'));
    }

    async function addSymbol() {
      const input = document.getElementById('new-symbol');
      const symbol = (input.value || '').toUpperCase().trim();
      if (!symbol) return;
      const r = await fetch('/api/symbols', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({symbol}) });
      const data = await r.json().catch(() => ({}));
      if (data.success) {
        input.value = '';
      } else {
        alert(data.error || 'Failed to add symbol');
      }
    }

    async function removeSymbol(symbol) {
      const r = await fetch('/api/symbols', { method:'DELETE', headers:{'Content-Type':'application/json'}, body: JSON.stringify({symbol}) });
      return await r.json().catch(() => ({}));
    }

    async function testTelegram() {
      const token = document.getElementById('telegram-token').value;
      const chat_id = document.getElementById('telegram-chat-id').value;
      const status = document.getElementById('telegram-status');
      if (!token || !chat_id) { status.textContent = 'Fill token + chat id'; return; }
      status.textContent = 'Sending...';
      const r = await fetch('/api/test-telegram', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({token, chat_id}) });
      const data = await r.json().catch(() => ({}));
      status.textContent = data.success ? '✅ Sent! Check Telegram.' : `❌ ${data.error || data.message || 'Failed'}`;
    }

    async function testEmail() {
      const status = document.getElementById('email-status');
      const cfg = {
        smtp_server: document.getElementById('email-smtp').value,
        smtp_port: document.getElementById('email-port').value,
        sender: document.getElementById('email-sender').value,
        password: document.getElementById('email-password').value,
        recipient: document.getElementById('email-recipient').value || document.getElementById('email-sender').value
      };
      if (!cfg.sender || !cfg.password) { status.textContent = 'Fill sender + app password'; return; }
      status.textContent = 'Sending...';
      const r = await fetch('/api/test-email', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(cfg) });
      const data = await r.json().catch(() => ({}));
      status.textContent = data.success ? '✅ Sent! Check inbox.' : `❌ ${data.error || data.message || 'Failed'}`;
    }

    // Notifications
    function requestNotificationPermission() {
      if (Notification.permission === 'default') Notification.requestPermission();
    }

    function playAlertSound() {
      const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBz2O0fPTgjMGHmzC8OShVBILTqvl7q5ZFQ1Tp+fys2oeBzaL0PPWgTMGIXDE8OWhUxIKTKvl7axYFg1Tp+fys2wdBzaK0PPWgTQGIXDE8OWhUxIKTKzl7axYFg1Sp+fys2wdBzaK0PPWgTQGIXDE8OWhUxIKTKzl7axYFg1Sp+fys2wdBzaK0PPWgTQGIXDE8OShVBILTazm7axYFg1Sp+fys2wcBzaK0PPWgTQGIXDE8OWhUxIKTKvl7axYFg1Sp+fys2wdBzaK0PPWgTQGIXDE8OWhUxIKTKzl7axYFg1Sp+fys2wdBzaK0PPWgTQGIXDE8OWhVBILTazl7axYFg1Tp+fys2wdBzaK0PPWgTQGIXDE8OWhUxIKTKvl7axYFg1Sp+fys2wdBzaK0PPWgTQGIXDE8OShVBILTazl7axYFg1Tp+fys2wdBzaK0PPWgTQGIXDE8OWhUxIKTKvl7axYFg1Sp+fys2wdBzaK0PPWgTQGIXDE8OWhUxIKTKzl7axYFg1Sp+fys2wdBzaK0PPWgTQGIXDE8OWhVBILTazl7axYFg1Sp+fys2wcBzaK0PPWgTQGIXDE8OWhUxIKTKvl7axYFg1Sp+fys2wdBzaK0PPWgTQGIXDE8OWhUxIKTKzl7axYFg1Sp+fys2wdBzaK0PPWgTQGIXDE8OWhVBILTazl7axYFg1Sp+fys2wdBzaK0PPWgTQGIXDE8OWhUxIKTKvl7axYFg1Sp+fys2wdBzaK0PPWgTQGIXDE8OWhUxIKTKzl7axYFg1Sp+fys2wdBzaK0PPWgTQG');
      audio.play().catch(() => {});
    }

    // Modal
    function openSymbolModal(symbol) {
      currentModalSymbol = symbol;
      document.getElementById('modal-title').textContent = symbol;
      document.getElementById('modal-backdrop').style.display = 'flex';
      document.body.style.overflow = 'hidden';

      refreshModal();
    }

    function closeModal(e) {
      document.getElementById('modal-backdrop').style.display = 'none';
      document.body.style.overflow = 'auto';
      currentModalSymbol = null;
      if (symbolChart) { symbolChart.destroy(); symbolChart = null; }
    }

    async function removeCurrentSymbol() {
      if (!currentModalSymbol) return;
      if (!confirm(`Remove ${currentModalSymbol}?`)) return;
      const out = await removeSymbol(currentModalSymbol);
      if (out.success) closeModal();
      else alert(out.error || 'Failed to remove symbol');
    }

    async function refreshModal() {
      if (!currentModalSymbol) return;
      await Promise.all([refreshModalStats(), refreshModalChart(), refreshModalSignals()]);
    }

    async function refreshModalStats() {
      const kv = document.getElementById('modal-kv');
      kv.innerHTML = '';
      try {
        const r = await fetch(`/api/symbol/${currentModalSymbol}/stats`);
        const data = await r.json();
        if (data.error) throw new Error(data.error);
        const info = data.info || {};

        const rows = [
          ['regularMarketPrice', info.regularMarketPrice != null ? `$${info.regularMarketPrice}` : (currentPrices[currentModalSymbol] ? `$${currentPrices[currentModalSymbol]}` : '--')],
          ['regularMarketChange', info.regularMarketChange != null ? `${info.regularMarketChange}` : '--'],
          ['regularMarketChangePercent', info.regularMarketChangePercent != null ? `${info.regularMarketChangePercent}%` : '--'],
          ['dayRange', (info.regularMarketDayLow!=null && info.regularMarketDayHigh!=null) ? `${info.regularMarketDayLow} - ${info.regularMarketDayHigh}` : '--'],
          ['52wRange', (info.fiftyTwoWeekLow!=null && info.fiftyTwoWeekHigh!=null) ? `${info.fiftyTwoWeekLow} - ${info.fiftyTwoWeekHigh}` : '--'],
          ['marketCap', info.marketCap != null ? fmtBig(info.marketCap) : '--'],
          ['trailingPE', info.trailingPE != null ? info.trailingPE : '--'],
          ['forwardPE', info.forwardPE != null ? info.forwardPE : '--'],
          ['dividendYield', info.dividendYield != null ? `${(info.dividendYield*100).toFixed(2)}%` : '--'],
          ['beta', info.beta != null ? info.beta : '--'],
          ['avgVolume', info.averageVolume != null ? fmtBig(info.averageVolume) : '--'],
          ['exchange', info.exchange || '--'],
        ];

        kv.innerHTML = rows.map(([k,v]) => `
          <div class="item" data-k="${k}">
            <div class="k">${niceKey(k)}</div>
            <div class="v">${v}</div>
          </div>
        `).join('');
      } catch (err) {
        kv.innerHTML = `<div class="muted">Failed to load stats: ${err}</div>`;
      }
    }

    async function refreshModalChart() {
      const status = document.getElementById('modal-chart-status');
      status.textContent = 'Loading...';
      try {
        const r = await fetch(`/api/prices/${currentModalSymbol}`);
        const data = await r.json();
        if (data.error) throw new Error(data.error);

        const labels = (data.timestamps || []).map(t => new Date(t).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}));
        const prices = data.prices || [];

        if (symbolChart) symbolChart.destroy();
        const ctx = document.getElementById('symbolChart');
        symbolChart = new Chart(ctx, {
          type: 'line',
          data: { labels, datasets: [{ label: currentModalSymbol, data: prices, pointRadius: 0, borderWidth: 2, tension: 0.15 }] },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
              y: { ticks: { color: '#cbd5e1' }, grid: { color: '#475569' } },
              x: { ticks: { color: '#cbd5e1', maxTicksLimit: 8 }, grid: { display: false } }
            }
          }
        });

        status.textContent = `${prices.length} pts`;
      } catch (err) {
        status.textContent = 'Failed';
      }
    }

    function refreshModalSignals() {
      const box = document.getElementById('modal-signals');
      const sym = currentModalSymbol;
      if (!sym) { box.textContent = '--'; return; }

      const s = symbolsData[sym];
      if (!s || !s.signals || s.signals.length === 0) {
        box.textContent = 'No signals yet today.';
        return;
      }

      box.innerHTML = s.signals.slice().reverse().map(sig => {
        const badge = sig.type === 'LONG' ? `<span class="pill open" style="border:none;">LONG</span>` : `<span class="pill closed" style="border:none;">SHORT</span>`;
        return `<div style="display:flex; justify-content: space-between; align-items:center; gap: .75rem; padding:.65rem; margin:.5rem 0; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px;">
          <div style="display:flex; flex-direction: column;">
            <div style="font-weight: 900;">${sig.time_display} ${badge}</div>
            <div class="muted">Entry ${sig.entry} • Stop ${sig.stop} • Target ${sig.target}</div>
          </div>
          <div style="font-weight: 900;">$${sig.price}</div>
        </div>`;
      }).join('');
    }

    // Helpers
    function niceKey(k) {
      const map = {
        regularMarketPrice: 'Price',
        regularMarketChange: 'Change',
        regularMarketChangePercent: 'Change %',
        dayRange: 'Day range',
        '52wRange': '52w range',
        marketCap: 'Market cap',
        trailingPE: 'Trailing P/E',
        forwardPE: 'Forward P/E',
        dividendYield: 'Dividend yield',
        beta: 'Beta',
        avgVolume: 'Avg volume',
        exchange: 'Exchange',
      };
      return map[k] || k;
    }

    function fmtBig(n) {
      const abs = Math.abs(Number(n));
      if (abs >= 1e12) return (n/1e12).toFixed(2) + 'T';
      if (abs >= 1e9) return (n/1e9).toFixed(2) + 'B';
      if (abs >= 1e6) return (n/1e6).toFixed(2) + 'M';
      if (abs >= 1e3) return (n/1e3).toFixed(2) + 'K';
      return String(n);
    }
  </script>
</body>
</html>"""


def main():
    import os

    templates_dir = "templates"
    os.makedirs(templates_dir, exist_ok=True)

    with open(f"{templates_dir}/dashboard_fused.html", "w", encoding="utf-8") as f:
        f.write(create_fused_dashboard_html())

    print("\n" + "=" * 78)
    print("ORB Scanner - Fused Pro+Control Dashboard")
    print("=" * 78)
    print("\n🌐 Open your browser and go to:")
    print("👉 http://localhost:5003")
    print("\n✨ Includes:")
    print("  • Pro dashboard look & layout")
    print("  • Add/remove symbols from UI")
    print("  • Telegram + Email notifications + connection tests")
    print("  • Multi-timezone market sessions with countdowns")
    print("  • Click symbol card for modal stats + intraday chart")
    print("\nPress Ctrl+C to stop")
    print("=" * 78 + "\n")

    socketio.run(app, host="0.0.0.0", port=5003, debug=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()