import pandas as pd
import pytest

from robo_advisor.returns import build_return_frames, compute_returns_wide


def test_simple_return_is_five_percent():
    prices = pd.DataFrame({"SPY": [100.0, 105.0]}, index=pd.to_datetime(["2020-01-02", "2020-01-03"]))
    returns = compute_returns_wide(prices)
    assert pd.isna(returns.iloc[0, 0])
    assert returns.iloc[1, 0] == pytest.approx(0.05)


def test_in_progress_snapshot_month_is_not_labeled_month_end():
    raw = pd.DataFrame({
        "date": pd.to_datetime(["2020-01-31", "2020-02-14"]),
        "ticker": ["SPY", "SPY"],
        "Adj Close": [100.0, 105.0],
    })
    frames = build_return_frames(raw, ["SPY"], snapshot_timestamp="2020-02-15T12:00:00+00:00")
    assert frames["adjusted_prices_monthly"]["month"].tolist() == ["2020-01"]


def test_monthly_frame_preserves_actual_last_trading_date():
    raw = pd.DataFrame({
        "date": pd.to_datetime(["2020-01-31", "2020-02-28"]),
        "ticker": ["SPY", "SPY"],
        "Adj Close": [100.0, 105.0],
    })
    frames = build_return_frames(raw, ["SPY"])
    monthly = frames["adjusted_prices_monthly"]
    february = monthly.loc[monthly["month"] == "2020-02"].iloc[0]
    assert february["month_end"] == pd.Timestamp("2020-02-29")
    assert february["price_observation_date"] == pd.Timestamp("2020-02-28")
