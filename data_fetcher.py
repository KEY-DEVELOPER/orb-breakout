"""
Data Fetcher for Stock Prices and Financial Data
Uses yfinance for stock data retrieval
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import List, Dict, Optional

import numpy as np
import pandas as pd
import yfinance as yf


class StockDataFetcher:
    """Fetch stock price and financial data"""

    def __init__(self, cache_dir: str = "./data"):
        """
        Initialize data fetcher

        Args:
            cache_dir: Directory to cache downloaded data (default ./data)
        """
        self.cache_dir = cache_dir
        self.prices_dir = os.path.join(cache_dir, "prices")
        self.earnings_dir = os.path.join(cache_dir, "earnings")
        os.makedirs(self.prices_dir, exist_ok=True)
        os.makedirs(self.earnings_dir, exist_ok=True)

    # ---------------------------
    # Helpers
    # ---------------------------
    @staticmethod
    def _clean_date_col(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"])
        # remove tz if any
        if hasattr(df["Date"].dt, "tz") and df["Date"].dt.tz is not None:
            df["Date"] = df["Date"].dt.tz_localize(None)
        return df

    def _price_path(self, ticker: str) -> str:
        return os.path.join(self.prices_dir, f"{ticker}_price.csv")

    def _earnings_path(self, ticker: str) -> str:
        return os.path.join(self.earnings_dir, f"{ticker}_earnings.csv")

    # ---------------------------
    # Price data (bulk)
    # ---------------------------
    def fetch_prices_bulk(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        interval: str = "1d",
        chunk_size: int = 200,
        auto_adjust: bool = False,
        overwrite: bool = False,
        min_rows: int = 100,
        pause_s: float = 0.5,
    ) -> List[str]:
        """
        Bulk download price data using yf.download for speed.

        Returns list of tickers successfully saved.
        """
        tickers = [t.strip().upper() for t in tickers if t.strip()]
        ok: List[str] = []

        # Skip already cached if not overwriting
        if not overwrite:
            tickers = [t for t in tickers if not os.path.exists(self._price_path(t))]

        if not tickers:
            return ok

        print(f"Bulk downloading prices for {len(tickers)} tickers...")

        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i : i + chunk_size]
            tick_str = " ".join(chunk)

            try:
                data = yf.download(
                    tick_str,
                    start=start_date,
                    end=end_date,
                    interval=interval,
                    group_by="ticker",
                    auto_adjust=auto_adjust,
                    threads=False,
                    progress=False,
                )
            except Exception as e:
                print(f"  Bulk download failed for chunk {i}-{i+len(chunk)-1}: {e}")
                continue

            # yf.download returns:
            # - MultiIndex columns when multiple tickers, columns like ('AAPL','Close')
            # - Single ticker DataFrame with columns Open/High/Low/Close/Adj Close/Volume
            for t in chunk:
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        if t not in data.columns.get_level_values(0):
                            continue
                        df_t = data[t].copy()
                    else:
                        # single ticker case (if chunk_size==1)
                        df_t = data.copy()

                    if df_t is None or df_t.empty:
                        continue

                    df_t = df_t.reset_index().rename(columns={"index": "Date"})
                    if "Date" not in df_t.columns:
                        # sometimes index is named already
                        df_t = df_t.reset_index()

                    # Standardize column names
                    keep = [c for c in ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"] if c in df_t.columns]
                    df_t = df_t[keep].copy()
                    df_t = self._clean_date_col(df_t)

                    # Prefer Close; if only Adj Close exists, map it
                    if "Close" not in df_t.columns and "Adj Close" in df_t.columns:
                        df_t["Close"] = df_t["Adj Close"]

                    needed = {"Date", "Close"}
                    if not needed.issubset(df_t.columns):
                        continue

                    df_t = df_t.dropna(subset=["Close"])
                    if len(df_t) < min_rows:
                        continue

                    out_path = self._price_path(t)
                    df_t.to_csv(out_path, index=False)
                    ok.append(t)

                except Exception:
                    continue

            time.sleep(pause_s)

        print(f"✓ Saved price data for {len(ok)} tickers into {self.prices_dir}")
        return ok

    def fetch_price_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        retry_count: int = 3
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical price data for a ticker (single ticker).

        Returns:
            DataFrame with OHLCV data or None
        """
        ticker = ticker.strip().upper()

        for attempt in range(retry_count):
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(start=start_date, end=end_date)

                if df is None or df.empty:
                    print(f"  Warning: No data for {ticker}")
                    return None

                df = df.reset_index()
                df = self._clean_date_col(df)

                cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
                df = df[cols].copy()
                return df

            except Exception as e:
                if attempt < retry_count - 1:
                    print(f"  Retry {attempt + 1}/{retry_count} for {ticker}: {str(e)}")
                    time.sleep(1)
                else:
                    print(f"  Failed to fetch {ticker}: {str(e)}")
                    return None

        return None

    # ---------------------------
    # Earnings (still per ticker)
    # ---------------------------
    def fetch_quarterly_earnings(
        self,
        ticker: str,
        retry_count: int = 3
    ) -> Optional[pd.DataFrame]:
        """
        Fetch quarterly earnings data (EPS) for a ticker.

        Returns:
            DataFrame with columns: Date, EPS or None
        """
        ticker = ticker.strip().upper()

        for attempt in range(retry_count):
            try:
                stock = yf.Ticker(ticker)

                # Try quarterly income stmt first
                try:
                    quarterly_income = stock.quarterly_income_stmt
                    if quarterly_income is not None and not quarterly_income.empty:
                        net_income = None
                        for col_name in [
                            "Net Income",
                            "Net Income Common Stockholders",
                            "NetIncome",
                            "Net Income Applicable To Common Shares",
                        ]:
                            if col_name in quarterly_income.index:
                                net_income = quarterly_income.loc[col_name]
                                break

                        if net_income is not None:
                            shares = None
                            try:
                                shares_value = stock.info.get("sharesOutstanding")
                                if shares_value and shares_value > 0:
                                    shares = float(shares_value)
                            except Exception:
                                shares = None

                            if shares:
                                eps_data = []
                                for date in net_income.index:
                                    ni = net_income[date]
                                    if pd.notna(ni):
                                        eps = float(ni) / shares
                                        if eps > 0:
                                            eps_data.append({"Date": pd.Timestamp(date), "EPS": eps})

                                if len(eps_data) >= 4:
                                    df = pd.DataFrame(eps_data)
                                    df["Date"] = pd.to_datetime(df["Date"])
                                    df = df.sort_values("Date").drop_duplicates("Date", keep="last")
                                    return df
                except Exception:
                    pass

                # Fallback: approximate from trailingEps
                try:
                    info = stock.info
                    trailing_eps = info.get("trailingEps")
                    if trailing_eps and float(trailing_eps) > 0:
                        hist = stock.history(period="3y")
                        if hist is not None and not hist.empty:
                            dates = pd.date_range(end=hist.index[-1], periods=12, freq="Q")
                            quarterly_eps = float(trailing_eps) / 4.0
                            eps_data = []
                            for i, date in enumerate(dates):
                                growth_factor = 1 + (i * 0.01)
                                eps = quarterly_eps * growth_factor
                                eps_data.append({"Date": pd.Timestamp(date), "EPS": eps})

                            df = pd.DataFrame(eps_data)
                            df["Date"] = pd.to_datetime(df["Date"])
                            df = df.sort_values("Date").drop_duplicates("Date", keep="last")
                            print(f"  Note: Using estimated quarterly EPS for {ticker} (TTM/4).")
                            return df
                except Exception:
                    pass

                print(f"  Could not fetch earnings data for {ticker}")
                return None

            except Exception as e:
                if attempt < retry_count - 1:
                    print(f"  Retry {attempt + 1}/{retry_count} for {ticker} earnings: {str(e)}")
                    time.sleep(1)
                else:
                    print(f"  Failed to fetch earnings for {ticker}: {str(e)}")
                    return None

        return None

    # ---------------------------
    # Save/load
    # ---------------------------
    def save_earnings_to_csv(self, ticker: str, earnings_df: pd.DataFrame) -> None:
        earnings_df = earnings_df.copy()
        earnings_df["Date"] = pd.to_datetime(earnings_df["Date"])
        earnings_df = earnings_df.sort_values("Date").drop_duplicates("Date", keep="last")
        earnings_df.to_csv(self._earnings_path(ticker), index=False)

    def load_price_from_csv(self, ticker: str) -> Optional[pd.DataFrame]:
        path = self._price_path(ticker)
        if not os.path.exists(path):
            return None
        df = pd.read_csv(path)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date")
        return df

    def load_earnings_from_csv(self, ticker: str) -> Optional[pd.DataFrame]:
        path = self._earnings_path(ticker)
        if not os.path.exists(path):
            return None
        df = pd.read_csv(path)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date")
        return df


def example_bulk_download():
    """
    Example: download prices for tickers from a text file and cache them.
    """
    tick_file = Path("all_tickers.txt")
    tickers = []
    if tick_file.exists():
        tickers = [
            line.split("#", 1)[0].strip().upper()
            for line in tick_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    fetcher = StockDataFetcher(cache_dir="./data")

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = "2005-01-01"  # longer history = more training rows

    ok = fetcher.fetch_prices_bulk(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        chunk_size=200,
        overwrite=False,
        min_rows=800,      # ~3 years of daily bars
        pause_s=0.25,
    )

    # Earnings fetch is slow; do it for tickers we got prices for
    for i, t in enumerate(ok, 1):
        print(f"[{i}/{len(ok)}] Earnings {t}...")
        eps = fetcher.fetch_quarterly_earnings(t)
        if eps is not None and len(eps) >= 4:
            fetcher.save_earnings_to_csv(t, eps)
        time.sleep(0.25)


if __name__ == "__main__":
    print("Stock Data Fetcher Module (bulk-capable)")
