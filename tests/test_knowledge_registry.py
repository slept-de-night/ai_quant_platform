"""
Unit tests for the FinancialKnowledgeRegistry and educational metric explanations.
"""

import pytest
from src.ai_quant.knowledge import (
    FinancialKnowledgeRegistry,
    FinancialMetricExplanation,
    MetricCategory,
    global_registry,
)


def test_all_core_metrics_registered():
    reg = global_registry()
    metrics = reg.all_metrics()
    assert len(metrics) >= 15, "Expected at least 15 comprehensive metric explanations"

    expected_ids = [
        "pe_ratio",
        "pb_ratio",
        "ev_ebitda",
        "fcf_yield",
        "peg_ratio",
        "altman_z_score",
        "piotroski_f_score",
        "beneish_m_score",
        "sloan_accruals",
        "sharpe_ratio",
        "sortino_ratio",
        "dsr",
        "pbo",
        "max_drawdown",
        "cvar_95",
        "barra_neutralization",
        "half_kelly",
        "ledoit_wolf_covariance",
        "volatility_targeting",
        "nbbo",
        "slippage",
        "exposure_reservations",
        "reconciliation",
        "interest_rate_differential",
        "gold_silver_ratio",
    ]

    for m_id in expected_ids:
        m = reg.get(m_id)
        assert m is not None, f"Metric '{m_id}' must be registered in FinancialKnowledgeRegistry"


def test_required_fields_present_and_well_formed():
    reg = global_registry()
    for m in reg.all_metrics():
        assert m.id, "Metric ID cannot be empty"
        assert m.name, f"Metric {m.id} missing name"
        assert m.category in MetricCategory, f"Metric {m.id} invalid category"
        assert len(m.summary) > 10, f"Metric {m.id} summary is too short"
        assert len(m.formula) > 0, f"Metric {m.id} formula is empty"
        assert len(m.interpretation) > 10, f"Metric {m.id} interpretation is too short"
        assert len(m.quant_usage) > 10, f"Metric {m.id} quant_usage is too short"
        assert len(m.pitfalls) > 10, f"Metric {m.id} pitfalls is too short"


def test_lookup_by_category():
    reg = global_registry()
    forensics = reg.list_by_category(MetricCategory.FORENSIC)
    assert len(forensics) >= 4
    forensic_ids = {m.id for m in forensics}
    assert "altman_z_score" in forensic_ids
    assert "piotroski_f_score" in forensic_ids
    assert "beneish_m_score" in forensic_ids
    assert "sloan_accruals" in forensic_ids

    risk_metrics = reg.list_by_category(MetricCategory.RISK)
    assert len(risk_metrics) >= 5
    risk_ids = {m.id for m in risk_metrics}
    assert "dsr" in risk_ids
    assert "pbo" in risk_ids
    assert "sharpe_ratio" in risk_ids


def test_search_functionality():
    reg = global_registry()
    # 1. Search by keyword in name
    res = reg.search("Altman")
    assert any(m.id == "altman_z_score" for m in res)

    # 2. Search by keyword in interpretation/summary
    res2 = reg.search("bankruptcy")
    assert any(m.id == "altman_z_score" for m in res2)

    # 3. Search by keyword in quant_usage
    res3 = reg.search("circuit breaker")
    assert any(m.id == "max_drawdown" for m in res3)

    # 4. Empty search returns all
    assert len(reg.search("")) == len(reg.all_metrics())
