import pandas as pd
from ai_quant.data import synthetic_bars
from ai_quant.features import feature_frame
from ai_quant.factors import compile_score, seed_strategies

def test_score_bounded():
    f = feature_frame(synthetic_bars("X", 600)).dropna()
    s = compile_score(f, seed_strategies()[0])
    assert s.max() <= 1 and s.min() >= -1


def test_cross_sectional_transformer():
    from ai_quant.quant.factors import CrossSectionalTransformer
    import numpy as np

    raw = pd.Series([10.0, 25.0, -5.0, 50.0, 12.0, 100.0, -30.0])
    ranks = CrossSectionalTransformer.cs_rank(raw, centered=True)
    assert len(ranks) == 7
    assert -0.6 <= ranks.min() <= 0.6
    assert -0.6 <= ranks.max() <= 0.6

    zscores = CrossSectionalTransformer.cs_zscore(raw, robust=True)
    assert len(zscores) == 7
    assert not zscores.isna().any()

    # Test neutralization against market beta & sector exposure
    exposures = pd.DataFrame({
        "beta": [1.0, 1.2, 0.8, 1.5, 0.9, 1.1, 0.7],
        "sector": [1, 1, 0, 1, 0, 0, 1],
    })
    residual = CrossSectionalTransformer.neutralize(raw, exposures)
    assert len(residual) == 7
    assert not residual.isna().any()

    # Test factor diagnostics
    forward_returns = pd.Series([0.02, 0.05, -0.01, 0.08, 0.01, 0.12, -0.04])
    diag = CrossSectionalTransformer.calculate_factor_diagnostics(raw, forward_returns)
    assert "ic" in diag
    assert "rank_ic" in diag
    assert "icir" in diag
    assert diag["rank_ic"] > 0

