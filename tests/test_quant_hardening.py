import numpy as np
import pandas as pd
from ai_quant.quant.factors import PolymorphicFactorNeutralizer
from ai_quant.quant.validation import compute_dsr, compute_pbo_from_folds


def test_deflated_sharpe_ratio_computation():
    # 1. Single trial / no variance -> baseline 0.5
    dsr_baseline = compute_dsr(observed_sharpe=1.5, sharpe_variance=0.0, n_trials=1, sample_length=504)
    assert dsr_baseline == 0.5

    # 2. Modest Sharpe across many trials (n=100) -> DSR deflated to lower confidence
    dsr_deflated = compute_dsr(observed_sharpe=0.8, sharpe_variance=0.25, n_trials=100, sample_length=504)
    assert dsr_deflated < 0.5

    # 3. Very strong Sharpe (Sharpe 3.5) with large sample length -> high DSR
    dsr_high = compute_dsr(observed_sharpe=3.5, sharpe_variance=0.20, n_trials=10, sample_length=1000)
    assert dsr_high > 0.80


def test_probability_of_backtest_overfitting():
    # Overfitted backtests: several negative out-of-sample folds
    folds_overfitted = [1.2, -0.4, 0.8, -0.2, -0.5, 0.6]
    pbo_high = compute_pbo_from_folds(folds_overfitted)
    assert 0.45 <= pbo_high <= 0.55

    # Robust strategy: all positive out-of-sample folds
    folds_robust = [1.2, 0.8, 0.9, 1.4, 0.5]
    pbo_zero = compute_pbo_from_folds(folds_robust)
    assert pbo_zero == 0.0


def test_polymorphic_factor_neutralization_equity():
    n = 100
    np.random.seed(42)
    market_beta = pd.Series(np.random.randn(n), index=pd.RangeIndex(n))
    factor_scores = 0.7 * market_beta + pd.Series(np.random.randn(n) * 0.3, index=pd.RangeIndex(n))

    neutralized = PolymorphicFactorNeutralizer.neutralize_equity(factor_scores, market_beta)
    # Correlation with market beta after neutralization should be near zero
    corr = float(neutralized.corr(market_beta))
    assert abs(corr) < 0.05


def test_polymorphic_factor_neutralization_crypto():
    n = 100
    np.random.seed(42)
    btc_beta = pd.Series(np.random.randn(n), index=pd.RangeIndex(n))
    factor_scores = 0.8 * btc_beta + pd.Series(np.random.randn(n) * 0.2, index=pd.RangeIndex(n))

    neutralized = PolymorphicFactorNeutralizer.neutralize_crypto(factor_scores, btc_beta)
    corr = float(neutralized.corr(btc_beta))
    assert abs(corr) < 0.05


def test_polymorphic_factor_neutralization_commodity():
    n = 100
    np.random.seed(42)
    dxy_beta = pd.Series(np.random.randn(n), index=pd.RangeIndex(n))
    real_yield_beta = pd.Series(np.random.randn(n), index=pd.RangeIndex(n))
    factor_scores = -0.6 * dxy_beta - 0.4 * real_yield_beta + pd.Series(np.random.randn(n) * 0.2, index=pd.RangeIndex(n))

    neutralized = PolymorphicFactorNeutralizer.neutralize_commodity(factor_scores, dxy_beta, real_yield_beta)
    corr_dxy = float(neutralized.corr(dxy_beta))
    corr_yield = float(neutralized.corr(real_yield_beta))
    assert abs(corr_dxy) < 0.05
    assert abs(corr_yield) < 0.05


def test_polymorphic_factor_neutralization_forex():
    n = 100
    np.random.seed(42)
    carry_diff = pd.Series(np.random.randn(n), index=pd.RangeIndex(n))
    factor_scores = 0.75 * carry_diff + pd.Series(np.random.randn(n) * 0.25, index=pd.RangeIndex(n))

    neutralized = PolymorphicFactorNeutralizer.neutralize_forex(factor_scores, carry_diff)
    corr = float(neutralized.corr(carry_diff))
    assert abs(corr) < 0.05
