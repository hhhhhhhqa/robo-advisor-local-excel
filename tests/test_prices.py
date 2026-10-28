import pandas as pd

from robo_advisor.returns import build_return_frames


def test_pre_inception_data_remains_missing():
    raw = pd.DataFrame({
        "date": pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-03"]),
        "ticker": ["SPY", "SPY", "GLD"],
        "Adj Close": [100.0, 101.0, 50.0],
    })
    frames = build_return_frames(raw, ["SPY", "GLD"])
    daily = frames["adjusted_prices_daily"]
    pre_inception = daily.loc[(daily["ticker"] == "GLD") & (daily["date"] == pd.Timestamp("2020-01-02")), "adjusted_close"]
    assert pre_inception.isna().all()
