import pytest

from robo_advisor.factors import parse_factor_csv_text


def test_ff3_percentage_is_converted_to_decimal():
    text = "Description\n,Mkt-RF,SMB,HML,RMW,CMA,RF\n202001,1.5,-0.5,0.25,9.9,8.8,0.10\n Annual Factors"
    factors = parse_factor_csv_text(text, "Emerging_FF3", "Emerging Markets", "Fama/French Emerging 5 Factors")
    assert factors.loc[0, "Mkt_RF"] == pytest.approx(0.015)
    assert factors.loc[0, "RF"] == pytest.approx(0.001)


def test_ff3_parser_rejects_non_numeric_monthly_value():
    text = "Description\n,Mkt-RF,SMB,HML,RF\n202001,1.5,not-a-number,0.25,0.10\n Annual Factors"
    with pytest.raises(ValueError, match="Invalid factor value"):
        parse_factor_csv_text(text, "US_FF3", "US")
