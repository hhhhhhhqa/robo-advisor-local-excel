import pandas as pd
import pytest

import robo_advisor.pipeline as pipeline


def test_validation_failure_prevents_final_write(monkeypatch):
    prices = pd.DataFrame({"date": [pd.Timestamp("2020-01-02")]})
    monkeypatch.setattr(
        pipeline,
        "load_project_config",
        lambda: {
            "assets": {"SPY": {}},
            "requested_start_date": "2020-01-01",
            "market_timezone": "America/New_York",
            "currency": "USD",
            "factor_availability_lag_months": 1,
        },
    )
    monkeypatch.setattr(pipeline, "ensure_directories", lambda: None)
    monkeypatch.setattr(
        pipeline,
        "download_prices",
        lambda *args, **kwargs: (prices, {"download_timestamp_utc": "2020-02-01T00:00:00Z"}),
    )
    monkeypatch.setattr(pipeline, "download_factor_sources", lambda **kwargs: None)
    monkeypatch.setattr(pipeline, "build_return_frames", lambda *args, **kwargs: {})
    monkeypatch.setattr(pipeline, "process_factor_sources", lambda: pd.DataFrame())
    monkeypatch.setattr(pipeline, "build_research_dataset", lambda *args, **kwargs: pd.DataFrame())

    def reject(*args, **kwargs):
        raise ValueError("invalid research data")

    monkeypatch.setattr(pipeline, "validate_research_data", reject)
    wrote_final = False

    def record_write(*args):
        nonlocal wrote_final
        wrote_final = True

    monkeypatch.setattr(pipeline, "atomic_write_parquet", record_write)

    with pytest.raises(ValueError, match="invalid research data"):
        pipeline.run_pipeline()
    assert not wrote_final
