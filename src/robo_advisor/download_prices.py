from __future__ import annotations

import json
import logging
import platform
import time
from datetime import datetime, timezone
from importlib.metadata import version

import pandas as pd
import yfinance as yf

from .config import METADATA_DIR, RAW_DIR
from .utils import atomic_write_json, atomic_write_parquet, sha256_file

LOGGER = logging.getLogger(__name__)
PRICE_COLUMNS = ["Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]


def _normalize_market_dates(
    index: pd.DatetimeIndex,
    market_timezone: str = "America/New_York",
) -> tuple[pd.DatetimeIndex, str | None]:
    source_timezone = str(index.tz) if index.tz is not None else None
    normalized = index
    if index.tz is not None:
        normalized = index.tz_convert(market_timezone).tz_localize(None)
    return normalized.normalize(), source_timezone


def _download_one(
    ticker: str,
    start: str,
    market_timezone: str = "America/New_York",
    attempts: int = 3,
) -> tuple[pd.DataFrame, str | None]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            frame = yf.Ticker(ticker).history(
                start=start,
                interval="1d",
                auto_adjust=False,
                actions=True,
                repair=False,
                raise_errors=True,
            )
            if frame.empty:
                raise RuntimeError("Yahoo Finance returned zero rows")
            dates, source_timezone = _normalize_market_dates(pd.DatetimeIndex(frame.index), market_timezone)
            frame = frame.copy()
            frame.index = dates
            frame.index.name = "date"
            for column in PRICE_COLUMNS:
                if column not in frame:
                    frame[column] = 0.0 if column in {"Dividends", "Stock Splits"} else pd.NA
            result = frame[PRICE_COLUMNS].reset_index()
            result.insert(1, "ticker", ticker)
            return result, source_timezone
        except Exception as exc:
            last_error = exc
            LOGGER.warning("Price download attempt %s/%s failed for %s: %s", attempt, attempts, ticker, exc)
            if attempt < attempts:
                time.sleep(attempt)
    raise RuntimeError(f"Yahoo Finance download failed for {ticker}: {last_error}") from last_error


def download_prices(
    tickers: list[str],
    start: str,
    refresh: bool = False,
    market_timezone: str = "America/New_York",
) -> tuple[pd.DataFrame, dict]:
    prices_path = RAW_DIR / "etf_prices.parquet"
    metadata_path = METADATA_DIR / "price_snapshot.json"

    if not refresh and prices_path.exists() and metadata_path.exists():
        LOGGER.info("Using local Yahoo raw snapshot (pass --refresh to replace it)")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        stored_timezone = metadata.get("market_timezone", "America/New_York")
        if stored_timezone != market_timezone:
            raise RuntimeError(
                f"Local price snapshot uses {stored_timezone}, but config requires {market_timezone}; "
                "rerun with --refresh."
            )
        return pd.read_parquet(prices_path), metadata

    cache_path = METADATA_DIR / "yfinance_cache"
    cache_path.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(cache_path))

    downloaded: list[pd.DataFrame] = []
    timezones: dict[str, str | None] = {}
    for ticker in tickers:
        LOGGER.info("Downloading Yahoo Finance daily history: %s", ticker)
        frame, source_timezone = _download_one(ticker, start, market_timezone=market_timezone)
        downloaded.append(frame)
        timezones[ticker] = source_timezone

    prices = pd.concat(downloaded, ignore_index=True)
    prices = prices.sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)
    atomic_write_parquet(prices, prices_path)

    per_ticker = {}
    for ticker, group in prices.groupby("ticker", sort=False):
        valid = group.loc[group["Adj Close"].notna(), "date"]
        per_ticker[ticker] = {
            "first_valid_date": valid.min(),
            "last_valid_date": valid.max(),
            "row_count": len(group),
            "adjusted_close_non_null_count": int(valid.size),
        }
    metadata = {
        "download_timestamp_utc": datetime.now(timezone.utc),
        "data_source": "Yahoo Finance via yfinance",
        "requested_start_date": start,
        "requested_end_date": "latest available",
        "market_timezone": market_timezone,
        "actual_start_date": prices["date"].min(),
        "actual_end_date": prices["date"].max(),
        "tickers": tickers,
        "python_version": platform.python_version(),
        "yfinance_version": version("yfinance"),
        "pandas_version": version("pandas"),
        "source_timezone_by_ticker": timezones,
        "row_counts": per_ticker,
        "price_file_sha256": sha256_file(prices_path),
    }
    atomic_write_json(metadata, metadata_path)
    return prices, metadata
