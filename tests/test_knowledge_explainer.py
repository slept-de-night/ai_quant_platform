"""
Unit tests for ContextualExplainer and cross-asset pedagogical explanations.
"""

import pytest
from src.ai_quant.knowledge.explainer import ContextualExplainer


def test_equity_altman_z_distress_explanation():
    explainer = ContextualExplainer()
    res = explainer.explain(
        metric_id="altman_z_score",
        value=1.45,
        symbol="MEME",
        asset_type="EQUITY",
        sector="Consumer Discretionary",
    )

    assert res["is_applicable"] is True
    assert res["zone"] == "Distress Zone"
    assert "Distress Zone" in res["assessment"]
    assert "Disqualified" in res["quant_impact"]


def test_equity_beneish_m_clean_explanation():
    explainer = ContextualExplainer()
    res = explainer.explain(
        metric_id="beneish_m_score",
        value=-2.85,
        symbol="AAPL",
        asset_type="EQUITY",
    )

    assert res["is_applicable"] is True
    assert res["zone"] == "Clean / Non-Manipulator"
    assert "cleared" in res["quant_impact"]


def test_cross_asset_crypto_rejection():
    explainer = ContextualExplainer()
    res = explainer.explain(
        metric_id="pe_ratio",
        value=None,
        symbol="BTC-USD",
        asset_type="CRYPTO",
    )

    assert res["is_applicable"] is False
    assert "NOT applicable to CRYPTO" in res["inapplicable_reason"]
    assert "Tokenomics" in res["recommended_alternative"]


def test_cross_asset_commodity_rejection():
    explainer = ContextualExplainer()
    res = explainer.explain(
        metric_id="altman_z_score",
        value=None,
        symbol="GLD",
        asset_type="COMMODITY",
    )

    assert res["is_applicable"] is False
    assert "NOT applicable to COMMODITY" in res["inapplicable_reason"]
    assert "Futures Term Structure" in res["recommended_alternative"]
