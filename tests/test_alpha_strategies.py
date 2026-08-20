import pytest
from ai_quant.quant.strategies import INSTITUTIONAL_ALPHA_STRATEGIES


def test_institutional_alpha_strategies():
    assert len(INSTITUTIONAL_ALPHA_STRATEGIES) == 3
    names = [s.name for s in INSTITUTIONAL_ALPHA_STRATEGIES]
    assert "vol_adjusted_cross_sectional_momentum" in names
    assert "mean_reversion_volume_exhaustion" in names
    assert "multi_horizon_trend_breakout" in names

    for s in INSTITUTIONAL_ALPHA_STRATEGIES:
        assert s.entry_threshold > s.exit_threshold
        assert len(s.terms) >= 3
        assert s.max_holding_days > 0
