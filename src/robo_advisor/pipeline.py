from __future__ import annotations

import argparse
import logging
import sys

from .alignment import build_research_dataset
from .config import FINAL_DIR, ensure_directories, load_project_config
from .download_factors import download_factor_sources
from .download_prices import download_prices
from .factors import process_factor_sources
from .returns import build_return_frames
from .utils import atomic_write_parquet, configure_logging
from .validation import validate_research_data

LOGGER = logging.getLogger(__name__)


def run_pipeline(refresh: bool = False) -> int:
    config = load_project_config()
    assets = config["assets"]
    tickers = list(assets)
    market_timezone = config["market_timezone"]
    return_currency = config["currency"]
    factor_availability_lag_months = config["factor_availability_lag_months"]
    ensure_directories()

    prices, price_metadata = download_prices(
        tickers,
        config["requested_start_date"],
        refresh=refresh,
        market_timezone=market_timezone,
    )
    download_factor_sources(refresh=refresh)
    frames = build_return_frames(
        prices,
        tickers,
        snapshot_timestamp=price_metadata["download_timestamp_utc"],
        market_timezone=market_timezone,
    )
    factors = process_factor_sources()
    dataset = build_research_dataset(
        frames,
        factors,
        assets,
        market_timezone=market_timezone,
        return_currency=return_currency,
        factor_availability_lag_months=factor_availability_lag_months,
    )

    summary = validate_research_data(
        prices,
        factors,
        dataset,
        assets,
        expected_market_timezone=market_timezone,
        expected_currency=return_currency,
        factor_availability_lag_months=factor_availability_lag_months,
    )
    output_path = FINAL_DIR / "research_dataset_monthly.parquet"
    atomic_write_parquet(dataset, output_path)

    LOGGER.info("Data pipeline completed")
    LOGGER.info("ETF universe: %s", ", ".join(tickers))
    LOGGER.info("Raw period: %s -> %s", prices["date"].min().date(), prices["date"].max().date())
    LOGGER.info("Final dataset: %s rows x %s columns", *dataset.shape)
    LOGGER.info("Rows awaiting published factors: %s", summary["unpublished_factor_rows"])
    LOGGER.info("Output: data/final/%s", output_path.name)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Robo Advisor research dataset")
    parser.add_argument("--refresh", action="store_true", help="Replace local Yahoo and FF3 snapshots")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    configure_logging(args.verbose)
    try:
        return run_pipeline(refresh=args.refresh)
    except Exception as exc:
        LOGGER.error("Pipeline failed: %s", exc)
        if args.verbose:
            LOGGER.exception("Detailed traceback")
        return 2


if __name__ == "__main__":
    sys.exit(main())
