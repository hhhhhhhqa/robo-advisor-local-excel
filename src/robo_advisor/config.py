from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "assets.json"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
RAW_FF3_DIR = RAW_DIR / "ff3"
METADATA_DIR = RAW_DIR / "metadata"
FINAL_DIR = DATA_DIR / "final"

FACTOR_SOURCES: dict[str, dict[str, str]] = {
    "US_FF3": {
        "region": "US",
        "source_dataset": "Fama/French 3 Factors",
        "url": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip",
    },
    "Europe_FF3": {
        "region": "Europe",
        "source_dataset": "Fama/French European 3 Factors",
        "url": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Europe_3_Factors_CSV.zip",
    },
    "Japan_FF3": {
        "region": "Japan",
        "source_dataset": "Fama/French Japanese 3 Factors",
        "url": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Japan_3_Factors_CSV.zip",
    },
    "Emerging_FF3": {
        "region": "Emerging Markets",
        "source_dataset": "Fama/French Emerging 5 Factors (Mkt-RF/SMB/HML/RF subset)",
        "url": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Emerging_5_Factors_CSV.zip",
    },
}


def load_project_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    assets = config.get("assets")
    if not isinstance(assets, dict) or not assets:
        raise ValueError("Config must define a non-empty assets mapping")
    if "requested_start_date" not in config:
        raise ValueError("Config is missing requested_start_date")
    market_timezone = config.get("market_timezone")
    if not isinstance(market_timezone, str) or not market_timezone:
        raise ValueError("Config must define a non-empty market_timezone")
    try:
        ZoneInfo(market_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Config references unknown market timezone: {market_timezone}") from exc
    currency = config.get("currency")
    if not isinstance(currency, str) or len(currency) != 3:
        raise ValueError("Config must define a three-letter currency")
    factor_lag = config.get("factor_availability_lag_months")
    if not isinstance(factor_lag, int) or factor_lag < 1:
        raise ValueError("factor_availability_lag_months must be a positive integer")

    for ticker, asset in assets.items():
        required = {"name", "asset_class", "region", "factor_model"}
        missing = required.difference(asset)
        if missing:
            raise ValueError(f"{ticker} is missing config keys: {sorted(missing)}")
        factor_model = asset["factor_model"]
        if factor_model is not None and factor_model not in FACTOR_SOURCES:
            raise ValueError(f"{ticker} references unknown factor model: {factor_model}")
    return config


def ensure_directories() -> None:
    for path in (RAW_DIR, RAW_FF3_DIR, METADATA_DIR, FINAL_DIR):
        path.mkdir(parents=True, exist_ok=True)
