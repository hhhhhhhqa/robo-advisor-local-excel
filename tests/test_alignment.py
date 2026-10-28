import pandas as pd

from robo_advisor.alignment import align_frames


def test_january_factor_aligns_only_to_january_return():
    prices = pd.DataFrame({
        "month": ["2020-01", "2020-02"],
        "month_end": pd.to_datetime(["2020-01-31", "2020-02-29"]),
        "ticker": ["SPY", "SPY"],
        "monthly_adjusted_close": [100.0, 101.0],
    })
    returns = prices[["month", "month_end", "ticker"]].copy()
    returns["monthly_return"] = [0.01, 0.02]
    factors = pd.DataFrame({
        "factor_model": ["US_FF3", "US_FF3"],
        "month": ["2020-01", "2020-02"],
        "source_dataset": ["Fama/French 3 Factors", "Fama/French 3 Factors"],
        "Mkt_RF": [0.11, 0.22], "SMB": [0.0, 0.0], "HML": [0.0, 0.0], "RF": [0.0, 0.0],
        "observation_month_end": pd.to_datetime(["2020-01-31", "2020-02-29"]),
    })
    assets = {"SPY": {"name": "US Large Cap", "asset_class": "equity", "region": "US", "factor_model": "US_FF3"}}
    aligned = align_frames(prices, returns, factors, assets)
    assert aligned.loc[aligned["month"] == "2020-01", "Mkt_RF"].item() == 0.11
    assert aligned.loc[aligned["month"] == "2020-02", "Mkt_RF"].item() == 0.22
