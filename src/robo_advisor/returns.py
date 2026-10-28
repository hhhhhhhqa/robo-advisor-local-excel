from __future__ import annotations

import pandas as pd


def compute_returns_wide(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change(fill_method=None)


def _wide_to_long(frame: pd.DataFrame, index_name: str, value_name: str) -> pd.DataFrame:
    """Reshape without dropping explicit NaNs, including pre-inception slots."""
    return (
        frame.rename_axis(index=index_name, columns="ticker")
        .reset_index()
        .melt(id_vars=index_name, var_name="ticker", value_name=value_name)
        .sort_values([index_name, "ticker"], kind="stable")
        .reset_index(drop=True)
    )


def build_return_frames(
    raw_prices: pd.DataFrame,
    tickers: list[str],
    snapshot_timestamp: str | pd.Timestamp | None = None,
    market_timezone: str = "America/New_York",
) -> dict[str, pd.DataFrame]:
    observed = raw_prices.pivot(index="date", columns="ticker", values="Adj Close").sort_index()
    adjusted_daily_wide = observed.reindex(columns=tickers)
    returns_daily_wide = compute_returns_wide(adjusted_daily_wide)

    monthly_index = adjusted_daily_wide.resample("ME").last().index.to_period("M")
    raw_with_month = raw_prices.copy()
    raw_with_month["month_period"] = raw_with_month["date"].dt.to_period("M")
    monthly_last = (
        raw_with_month.loc[raw_with_month["Adj Close"].notna(), ["month_period", "ticker", "date", "Adj Close"]]
        .sort_values(["month_period", "ticker", "date"], kind="stable")
        .drop_duplicates(["month_period", "ticker"], keep="last")
    )
    monthly_last_price = monthly_last.pivot(index="month_period", columns="ticker", values="Adj Close")
    monthly_observation_date = monthly_last.pivot(index="month_period", columns="ticker", values="date")
    adjusted_monthly_wide = monthly_last_price.reindex(index=monthly_index, columns=tickers)
    monthly_observation_date = monthly_observation_date.reindex(index=monthly_index, columns=tickers)
    adjusted_monthly_wide.index = adjusted_monthly_wide.index.to_timestamp(how="end").normalize()
    monthly_observation_date.index = monthly_observation_date.index.to_timestamp(how="end").normalize()
    if snapshot_timestamp is not None:
        snapshot = pd.Timestamp(snapshot_timestamp)
        if snapshot.tzinfo is not None:
            snapshot = snapshot.tz_convert(market_timezone).tz_localize(None)
        snapshot_month = snapshot.to_period("M")
        adjusted_monthly_wide = adjusted_monthly_wide.loc[adjusted_monthly_wide.index.to_period("M") < snapshot_month]
        monthly_observation_date = monthly_observation_date.loc[
            monthly_observation_date.index.to_period("M") < snapshot_month
        ]
    returns_monthly_wide = compute_returns_wide(adjusted_monthly_wide)

    adjusted_daily = _wide_to_long(adjusted_daily_wide, "date", "adjusted_close")
    returns_daily = _wide_to_long(returns_daily_wide, "date", "daily_return")
    adjusted_monthly = _wide_to_long(adjusted_monthly_wide, "month_end", "monthly_adjusted_close")
    observation_dates = _wide_to_long(monthly_observation_date, "month_end", "price_observation_date")
    adjusted_monthly = adjusted_monthly.merge(observation_dates, on=["month_end", "ticker"], how="left", validate="one_to_one")
    adjusted_monthly["month"] = adjusted_monthly["month_end"].dt.to_period("M").astype(str)
    returns_monthly = _wide_to_long(returns_monthly_wide, "month_end", "monthly_return")
    returns_monthly = returns_monthly.merge(observation_dates, on=["month_end", "ticker"], how="left", validate="one_to_one")
    returns_monthly["month"] = returns_monthly["month_end"].dt.to_period("M").astype(str)

    return {
        "adjusted_prices_daily": adjusted_daily[["date", "ticker", "adjusted_close"]],
        "returns_daily": returns_daily[["date", "ticker", "daily_return"]],
        "adjusted_prices_monthly": adjusted_monthly[
            ["month", "month_end", "ticker", "monthly_adjusted_close", "price_observation_date"]
        ],
        "returns_monthly": returns_monthly[
            ["month", "month_end", "ticker", "monthly_return", "price_observation_date"]
        ],
    }
