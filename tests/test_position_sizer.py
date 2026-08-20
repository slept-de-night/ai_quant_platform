import pytest
from ai_quant.quant.position_sizer import DynamicPositionSizer


def test_dynamic_position_sizer():
    sizer = DynamicPositionSizer(
        target_annual_vol=0.15,
        max_position_pct=0.08,
        cash_reserve_pct=0.10,
    )
    result = sizer.calculate_size(
        signal_score=0.72,
        equity=1_000_000,
        reference_price=125.50,
        realized_vol_20d=0.012,
        win_rate=0.56,
        payoff_ratio=1.7,
    )
    assert result["side"] == "LONG"
    assert result["quantity"] > 0
    assert result["notional"] <= 1_000_000 * 0.08
    assert result["capped_position_fraction"] <= 0.08
    assert result["half_kelly_fraction"] > 0
