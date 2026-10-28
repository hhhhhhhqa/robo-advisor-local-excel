"""Daily market snapshots used by the Excel trading simulator."""

from __future__ import annotations

from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone
from math import isfinite
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from .download_prices import _download_one
from .utils import atomic_write_parquet


FX_SYMBOLS = {
    "JPY": ("JPY=X", True),       # Yahoo quotes JPY per USD.
    "EUR": ("EURUSD=X", False),   # Yahoo quotes USD per EUR.
    "AUD": ("AUDUSD=X", False),   # Yahoo quotes USD per AUD.
    "CNY": ("CNY=X", True),       # Yahoo quotes CNY per USD.
}
FX_CURRENCIES = ("USD", "JPY", "EUR", "AUD", "CNY")
MAX_FX_AGE_DAYS = 5


def _merge_snapshot(existing: pd.DataFrame, new: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    frames = [frame for frame in (existing, new) if not frame.empty]
    if not frames:
        return existing.copy()
    merged = pd.concat(frames, ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"]).dt.normalize()
    return merged.drop_duplicates(keys, keep="last").sort_values(keys, kind="stable").reset_index(drop=True)


def load_price_snapshot(path: Path, refresh: bool, tickers: list[str], start: str,
                        seed_path: Path | None = None) -> pd.DataFrame:
    if path.exists():
        existing = pd.read_parquet(path)
    elif seed_path is not None and seed_path.exists():
        existing = pd.read_parquet(seed_path)
    else:
        existing = pd.DataFrame(columns=["date", "ticker", "Close"])
    today_new_york = datetime.now(ZoneInfo("America/New_York")).date()
    existing = existing.loc[pd.to_datetime(existing["date"]).dt.date < today_new_york].copy()
    if not refresh:
        if existing.empty:
            raise FileNotFoundError("ETF price cache is missing. Select Yes for Update ETF prices and rerun.")
        return existing
    frames = []
    for ticker in tickers:
        history = existing.loc[existing["ticker"] == ticker] if not existing.empty else existing
        from_date = (pd.Timestamp(history["date"].max()).date() - timedelta(days=7)).isoformat() if not history.empty else start
        frame, _ = _download_one(ticker, from_date)
        frame = frame.loc[pd.to_datetime(frame["date"]).dt.date < today_new_york]
        frames.append(frame)
    refreshed = _merge_snapshot(existing, pd.concat(frames, ignore_index=True), ["ticker", "date"])
    atomic_write_parquet(refreshed, path)
    return refreshed


def load_fx_snapshot(path: Path, refresh: bool, start: str) -> pd.DataFrame:
    existing = pd.read_parquet(path) if path.exists() else pd.DataFrame(columns=["date", "currency", "usd_per_unit", "symbol"])
    today_utc = datetime.now(timezone.utc).date()
    existing = existing.loc[pd.to_datetime(existing["date"]).dt.date < today_utc].copy()
    if not refresh:
        return existing
    frames = []
    for currency, (symbol, inverse) in FX_SYMBOLS.items():
        history = existing.loc[existing["currency"] == currency] if not existing.empty else existing
        from_date = (pd.Timestamp(history["date"].max()).date() - timedelta(days=7)).isoformat() if not history.empty else start
        raw = yf.Ticker(symbol).history(start=from_date, interval="1d", auto_adjust=False, raise_errors=True)
        raw = raw.loc[pd.DatetimeIndex(raw.index).tz_localize(None).date < today_utc]
        if raw.empty:
            raise RuntimeError(f"No Yahoo Finance FX data for {symbol}")
        close = pd.to_numeric(raw["Close"], errors="coerce")
        if close.isna().any() or (close <= 0).any() or not close.map(isfinite).all():
            raise ValueError(f"Invalid Yahoo Finance FX close for {symbol}")
        dates = pd.DatetimeIndex(raw.index).tz_localize(None).normalize()
        rates = 1 / close.to_numpy() if inverse else close.to_numpy()
        frames.append(pd.DataFrame({"date": dates, "currency": currency,
                                    "usd_per_unit": rates, "symbol": symbol}))
    refreshed = _merge_snapshot(existing, pd.concat(frames, ignore_index=True), ["currency", "date"])
    atomic_write_parquet(refreshed, path)
    return refreshed


class MarketData:
    def __init__(self, prices: pd.DataFrame, fx: pd.DataFrame):
        self.prices: dict[tuple[date, str], float] = {}
        for row in prices.itertuples(index=False):
            if pd.notna(row.Close) and isfinite(float(row.Close)) and float(row.Close) > 0:
                self.prices[(pd.Timestamp(row.date).date(), row.ticker)] = float(row.Close)
        self.price_dates = sorted({day for day, _ in self.prices})
        self.fx: dict[str, list[tuple[date, float]]] = {}
        for row in fx.itertuples(index=False):
            value = float(row.usd_per_unit)
            if not isfinite(value) or value <= 0:
                raise ValueError(f"Invalid FX rate for {row.currency}")
            self.fx.setdefault(row.currency, []).append((pd.Timestamp(row.date).date(), value))
        for rates in self.fx.values():
            rates.sort()
        self.fx_dates = {currency: [day for day, _ in rates] for currency, rates in self.fx.items()}

    def close(self, day: date, ticker: str) -> float:
        try:
            return self.prices[(day, ticker)]
        except KeyError as exc:
            raise ValueError(f"No ETF close for {ticker} on {day}; update prices or choose a trading day") from exc

    def usd_per_unit(self, day: date, currency: str) -> tuple[float, date]:
        if currency == "USD":
            return 1.0, day
        rates = self.fx.get(currency, [])
        index = bisect_right(self.fx_dates.get(currency, []), day) - 1
        if index < 0:
            raise ValueError(f"No {currency}/USD FX rate on or before {day}; update FX rates")
        rate_day, rate = rates[index]
        if (day - rate_day).days > MAX_FX_AGE_DAYS:
            raise ValueError(f"{currency}/USD FX rate is stale on {day} (last {rate_day})")
        return rate, rate_day
