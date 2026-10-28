from __future__ import annotations

import pandas as pd

FINAL_COLUMNS = [
    "month", "month_end", "price_observation_date", "ticker", "name", "asset_class", "region", "factor_model",
    "monthly_adjusted_close", "monthly_return", "source_dataset", "Mkt_RF", "SMB", "HML", "RF",
    "observation_month_end", "factor_available_month", "information_available_at", "decision_month", "holding_month",
    "market_timezone", "return_currency",
    "availability_assumption",
]


def add_temporal_fields(frame: pd.DataFrame, factor_availability_lag_months: int = 1) -> pd.DataFrame:
    result = frame.copy()
    periods = pd.PeriodIndex(result["month"], freq="M")
    month_end = periods.to_timestamp(how="end").normalize()
    factor_available_periods = periods + factor_availability_lag_months
    result["factor_available_month"] = factor_available_periods.astype(str)
    result["information_available_at"] = factor_available_periods.to_timestamp(how="start")
    result["decision_month"] = (periods + 1).astype(str)
    result["holding_month"] = result["decision_month"]
    result["availability_assumption"] = (
        f"factor_observation_month_plus_{factor_availability_lag_months}_month; source release date unverified"
    )
    return result


def align_frames(
    monthly_prices: pd.DataFrame,
    monthly_returns: pd.DataFrame,
    factors: pd.DataFrame,
    assets: dict,
    market_timezone: str = "America/New_York",
    return_currency: str = "USD",
    factor_availability_lag_months: int = 1,
) -> pd.DataFrame:
    base = monthly_prices.merge(
        monthly_returns[["month", "ticker", "monthly_return"]],
        on=["month", "ticker"],
        how="left",
        validate="one_to_one",
    )
    metadata = pd.DataFrame.from_dict(assets, orient="index").rename_axis("ticker").reset_index()
    base = base.merge(metadata, on="ticker", how="left", validate="many_to_one")
    factor_columns = ["factor_model", "month", "source_dataset", "Mkt_RF", "SMB", "HML", "RF", "observation_month_end"]
    aligned = base.merge(factors[factor_columns], on=["factor_model", "month"], how="left", validate="many_to_one")
    aligned = add_temporal_fields(aligned, factor_availability_lag_months)
    aligned["market_timezone"] = market_timezone
    aligned["return_currency"] = return_currency
    return aligned.sort_values(["month", "ticker"], kind="stable").reset_index(drop=True)


def build_research_dataset(
    frames: dict[str, pd.DataFrame],
    factors: pd.DataFrame,
    assets: dict,
    market_timezone: str = "America/New_York",
    return_currency: str = "USD",
    factor_availability_lag_months: int = 1,
) -> pd.DataFrame:
    aligned = align_frames(
        frames["adjusted_prices_monthly"],
        frames["returns_monthly"],
        factors,
        assets,
        market_timezone=market_timezone,
        return_currency=return_currency,
        factor_availability_lag_months=factor_availability_lag_months,
    )
    return aligned[FINAL_COLUMNS].copy()
