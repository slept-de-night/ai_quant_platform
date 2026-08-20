import pytest
from ai_quant.intelligence.forensics import calculate_beneish_m_score, calculate_sloan_accrual_anomaly


def test_beneish_m_score_safe():
    cur = {
        "sales": 100.0,
        "receivables": 15.0,
        "cogs": 40.0,
        "current_assets": 50.0,
        "cash": 20.0,
        "ppe": 30.0,
        "total_assets": 120.0,
        "depreciation": 5.0,
        "sga": 18.0,
        "current_liabilities": 25.0,
        "long_term_debt": 20.0,
        "net_income": 25.0,
        "operating_cash_flow": 30.0,
    }
    prev = {
        "sales": 90.0,
        "receivables": 14.0,
        "cogs": 38.0,
        "current_assets": 45.0,
        "cash": 18.0,
        "ppe": 28.0,
        "total_assets": 110.0,
        "depreciation": 4.5,
        "sga": 16.5,
        "current_liabilities": 24.0,
        "long_term_debt": 22.0,
        "net_income": 22.0,
        "operating_cash_flow": 28.0,
    }
    res = calculate_beneish_m_score(cur, prev)
    assert "m_score" in res
    assert "zone" in res
    assert "ratios" in res
    assert res["m_score"] < -1.78
    assert res["zone_color"] == "emerald"


def test_sloan_accruals():
    financials = {
        "net_income": 20.0,
        "operating_cash_flow": 28.0,
        "total_assets": 100.0,
    }
    res = calculate_sloan_accrual_anomaly(financials)
    assert "accruals" in res
    assert "accrual_ratio" in res
    assert res["accruals"] == -8.0
    assert res["accrual_ratio"] == -0.08
    assert res["quality"] == "High Quality (Cash-Backed)"
