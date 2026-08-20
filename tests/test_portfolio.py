import pytest
import numpy as np
import pandas as pd
from ai_quant.quant.portfolio import PortfolioOptimizer


def test_portfolio_optimizer():
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=100)
    returns_df = pd.DataFrame(
        {
            "AAPL": np.random.normal(0.0008, 0.015, 100),
            "MSFT": np.random.normal(0.0007, 0.014, 100),
            "NVDA": np.random.normal(0.0015, 0.025, 100),
            "SPY": np.random.normal(0.0004, 0.010, 100),
        },
        index=dates,
    )

    expected_returns = {
        "AAPL": 0.12,
        "MSFT": 0.10,
        "NVDA": 0.25,
        "SPY": 0.08,
    }

    optimizer = PortfolioOptimizer(
        target_annual_vol=0.15,
        max_single_weight=0.08,
        max_gross_exposure=0.60,
    )

    res = optimizer.optimize_weights(expected_returns, returns_df)

    assert "weights" in res
    assert "portfolio_vol" in res
    assert "gross_exposure" in res
    assert res["gross_exposure"] <= 0.60 + 1e-4

    for sym, weight in res["weights"].items():
        assert 0.0 <= weight <= 0.08 + 1e-4
