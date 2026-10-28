from __future__ import annotations

from typing import Any

import pandas as pd

PRICE_COLUMNS = {"date", "ticker", "Adj Close"}
FACTOR_COLUMNS = {"factor_model", "month", "Mkt_RF", "SMB", "HML", "RF"}
DATASET_COLUMNS = {
    "ticker", "month", "asset_class", "factor_model", "monthly_return",
    "price_observation_date", "Mkt_RF", "SMB", "HML", "RF",
    "factor_available_month", "decision_month", "market_timezone", "return_currency",
}


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{label} is missing columns: {sorted(missing)}")


def validate_research_data(
    prices: pd.DataFrame,
    factors: pd.DataFrame,
    dataset: pd.DataFrame,
    assets: dict[str, dict[str, Any]],
    expected_market_timezone: str | None = None,
    expected_currency: str | None = None,
    factor_availability_lag_months: int = 1,
) -> dict[str, int]:
    """Reject structural or research-design errors before the final dataset is saved."""
    _require_columns(prices, PRICE_COLUMNS, "Prices")
    _require_columns(factors, FACTOR_COLUMNS, "Factors")
    _require_columns(dataset, DATASET_COLUMNS, "Research dataset")

    errors: list[str] = []
    tickers = list(assets)

    if prices.duplicated(["ticker", "date"]).any():
        errors.append("prices contain duplicate ticker-date rows")
    observed = set(prices.loc[prices["Adj Close"].notna(), "ticker"])
    if missing := set(tickers).difference(observed):
        errors.append(f"tickers without adjusted-close data: {sorted(missing)}")
    if prices["Adj Close"].dropna().le(0).any():
        errors.append("prices contain non-positive adjusted closes")

    factor_fields = ["Mkt_RF", "SMB", "HML", "RF"]
    if factors.duplicated(["factor_model", "month"]).any():
        errors.append("factors contain duplicate factor_model-month rows")
    if factors[factor_fields].isna().any().any():
        errors.append("factor source contains missing factor values")
    if factors[factor_fields].abs().max().max() >= 1:
        errors.append("factor values appear not to be decimal returns")

    if dataset.duplicated(["ticker", "month"]).any():
        errors.append("research dataset contains duplicate ticker-month rows")
    if set(dataset["ticker"].dropna()) != set(tickers):
        errors.append("research dataset ticker universe differs from config/assets.json")

    expected_models = dataset["ticker"].map({ticker: item["factor_model"] for ticker, item in assets.items()})
    actual_models = dataset["factor_model"]
    mapping_mismatch = actual_models.fillna("NONE").ne(expected_models.fillna("NONE"))
    if mapping_mismatch.any():
        errors.append("research dataset does not match the configured asset-factor mapping")

    periods = pd.PeriodIndex(dataset["month"], freq="M")
    decisions = pd.PeriodIndex(dataset["decision_month"], freq="M")
    if not (decisions == periods + 1).all():
        errors.append("decision_month must be exactly one month after observation month")

    factor_available = pd.PeriodIndex(dataset["factor_available_month"], freq="M")
    if not (factor_available == periods + factor_availability_lag_months).all():
        errors.append("factor_available_month does not match the configured availability lag")

    observation_dates = pd.to_datetime(dataset["price_observation_date"], errors="coerce")
    observed_prices = observation_dates.notna()
    if observed_prices.any():
        observation_periods = observation_dates[observed_prices].dt.to_period("M").astype(str)
        if not observation_periods.eq(dataset.loc[observed_prices, "month"]).all():
            errors.append("price observation dates must belong to their labeled month")
        month_ends = pd.to_datetime(dataset.loc[observed_prices, "month_end"])
        if (observation_dates[observed_prices] > month_ends).any():
            errors.append("price observation dates cannot be after the labeled month end")

    if dataset["market_timezone"].isna().any() or dataset["market_timezone"].nunique() != 1:
        errors.append("research dataset must use one market timezone")
    elif expected_market_timezone and dataset["market_timezone"].iat[0] != expected_market_timezone:
        errors.append("research dataset market timezone differs from config")
    if dataset["return_currency"].isna().any() or dataset["return_currency"].nunique() != 1:
        errors.append("research dataset must use one return currency")
    elif expected_currency and dataset["return_currency"].iat[0] != expected_currency:
        errors.append("research dataset return currency differs from config")

    equity = actual_models.notna() & dataset["monthly_return"].notna()
    missing_factors = equity & dataset[factor_fields].isna().any(axis=1)
    published_keys = set(zip(factors["factor_model"], factors["month"], strict=True))
    missing_with_source = missing_factors & pd.Series(
        [(model, month) in published_keys for model, month in zip(actual_models, dataset["month"], strict=True)],
        index=dataset.index,
    )
    if missing_with_source.any():
        errors.append("published factor rows failed to join to equity returns")

    non_equity_with_factors = actual_models.isna() & dataset[factor_fields].notna().any(axis=1)
    if non_equity_with_factors.any():
        errors.append("non-equity assets were assigned equity factor values")

    if errors:
        raise ValueError("Data validation failed: " + "; ".join(errors))

    return {
        "price_rows": len(prices),
        "factor_rows": len(factors),
        "dataset_rows": len(dataset),
        "unpublished_factor_rows": int(missing_factors.sum()),
    }
