import pandas as pd

from robo_advisor.alignment import add_temporal_fields


def test_observation_month_only_informs_later_decision():
    frame = add_temporal_fields(pd.DataFrame({"month": ["2020-01", "2020-12"]}))
    observation = pd.PeriodIndex(frame["month"], freq="M")
    decision = pd.PeriodIndex(frame["decision_month"], freq="M")
    assert (decision > observation).all()
    assert frame["decision_month"].tolist() == ["2020-02", "2021-01"]
    assert frame["factor_available_month"].tolist() == ["2020-02", "2021-01"]
    assert frame["information_available_at"].dt.strftime("%Y-%m-%d").tolist() == ["2020-02-01", "2021-01-01"]
