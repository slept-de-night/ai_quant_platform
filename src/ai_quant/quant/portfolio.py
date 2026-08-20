from __future__ import annotations

from typing import Dict, Tuple, List, Optional, Any
import numpy as np
import pandas as pd

from ..core.models import BacktestMetrics, StrategySpec
from ..data.features import feature_frame
from .backtest import metrics_from_returns, run_backtest


class PortfolioOptimizer:
    """Institutional Factor Covariance & Constrained Portfolio Optimizer."""

    def __init__(
        self,
        target_annual_vol: float = 0.15,
        max_single_weight: float = 0.08,
        max_gross_exposure: float = 0.80,
        min_cash_reserve: float = 0.10,
        risk_aversion: float = 1.0,
    ) -> None:
        self.target_annual_vol = target_annual_vol
        self.max_single_weight = max_single_weight
        self.max_gross_exposure = max_gross_exposure
        self.min_cash_reserve = min_cash_reserve
        self.risk_aversion = risk_aversion

    @staticmethod
    def estimate_shrinkage_covariance(
        returns_df: pd.DataFrame,
        shrinkage_factor: float = 0.20,
    ) -> np.ndarray:
        """Ledoit-Wolf style shrinkage covariance estimator."""
        sample_cov = returns_df.cov().values * 252.0  # Annualized
        n = sample_cov.shape[0]
        if n <= 1:
            return np.atleast_2d(sample_cov)
        diag = np.diag(np.diag(sample_cov))
        target_cov = np.eye(n) * np.mean(np.diag(sample_cov))
        shrunk_cov = (1.0 - shrinkage_factor) * sample_cov + shrinkage_factor * target_cov
        return shrunk_cov

    def optimize_weights(
        self,
        expected_returns: Dict[str, float],
        returns_history: pd.DataFrame,
        current_weights: Optional[Dict[str, float]] = None,
        transaction_cost_bps: float = 10.0,
    ) -> Dict[str, Any]:
        """Compute optimal risk-adjusted portfolio weights subject to covariance and capacity constraints."""
        symbols = list(expected_returns.keys())
        n = len(symbols)
        if n == 0:
            return {"weights": {}, "portfolio_vol": 0.0, "expected_return": 0.0}

        mu = np.array([expected_returns[s] for s in symbols])
        history = returns_history[symbols].dropna()
        if len(history) < 20:
            # Fallback to equal weight capped
            eq_w = min(self.max_single_weight, self.max_gross_exposure / max(n, 1))
            return {
                "weights": {s: eq_w for s in symbols},
                "portfolio_vol": self.target_annual_vol,
                "expected_return": float(np.mean(mu)),
            }

        cov = self.estimate_shrinkage_covariance(history)
        
        # Closed-form regularized mean-variance with L2 ridge: w = (lambda * Cov + gamma * I)^(-1) mu
        reg_cov = self.risk_aversion * cov + 1e-4 * np.eye(n)
        try:
            raw_w = np.linalg.solve(reg_cov, mu)
        except Exception:
            raw_w = np.ones(n) / n

        # Long-only projection
        raw_w = np.maximum(0, raw_w)
        if np.sum(raw_w) > 1e-6:
            raw_w = raw_w / np.sum(raw_w)
        else:
            raw_w = np.ones(n) / n

        # Apply single-name caps
        capped_w = np.minimum(raw_w, self.max_single_weight)

        # Portfolio-level volatility calculation: sigma_p = sqrt(w^T * Cov * w)
        port_var = float(capped_w.T @ cov @ capped_w)
        port_vol = np.sqrt(max(port_var, 1e-6))

        # True portfolio volatility scaling
        if port_vol > 1e-4:
            vol_scale = min(1.5, self.target_annual_vol / port_vol)
            scaled_w = capped_w * vol_scale
        else:
            scaled_w = capped_w

        # Re-enforce single name cap and gross exposure cap
        scaled_w = np.minimum(scaled_w, self.max_single_weight)
        gross_w = np.sum(scaled_w)
        if gross_w > self.max_gross_exposure:
            scaled_w = scaled_w * (self.max_gross_exposure / gross_w)

        # Build output weight dict
        weight_dict = {symbols[i]: round(float(scaled_w[i]), 4) for i in range(n)}
        expected_port_ret = float(np.sum(scaled_w * mu))

        return {
            "weights": weight_dict,
            "portfolio_vol": round(float(port_vol), 4),
            "expected_return": round(expected_port_ret, 4),
            "gross_exposure": round(float(np.sum(scaled_w)), 4),
            "cash_reserve": round(1.0 - float(np.sum(scaled_w)), 4),
        }


def portfolio_backtest(
    data: Dict[str, pd.DataFrame],
    spec: StrategySpec,
    max_symbol_weight: float = 0.20,
    gross_target: float = 0.80,
    slippage_bps: float = 5,
) -> Tuple[BacktestMetrics, pd.DataFrame]:
    """Execute inverse-volatility weighted multi-asset portfolio simulation."""
    positions = {}
    rets = {}
    vols = {}
    common_index = None

    for sym, bars in data.items():
        f = feature_frame(bars).dropna()
        _, detail = run_backtest(bars, spec, slippage_bps=0, commission_bps=0)
        positions[sym] = detail["position"]
        rets[sym] = f["close"].pct_change()
        vols[sym] = f["vol_20"]
        common_index = detail.index if common_index is None else common_index.intersection(detail.index)

    pos = pd.DataFrame(positions).reindex(common_index).fillna(0)
    ret = pd.DataFrame(rets).reindex(common_index).fillna(0)
    vol = pd.DataFrame(vols).reindex(common_index).ffill().shift(1).clip(lower=0.05)

    invvol = (1 / vol) * pos
    denom = invvol.sum(axis=1).replace(0, np.nan)
    w = invvol.div(denom, axis=0).fillna(0) * gross_target
    w = w.clip(upper=max_symbol_weight)

    row_sum = w.sum(axis=1)
    scale = (gross_target / row_sum).clip(upper=1).replace([np.inf, -np.inf], 0).fillna(0)
    w = w.mul(scale, axis=0)
    exec_w = w.fillna(0)

    turnover = exec_w.diff().abs().sum(axis=1).fillna(exec_w.abs().sum(axis=1))
    strat = (exec_w * ret).sum(axis=1) - turnover * (slippage_bps / 10000)
    bench = ret.mean(axis=1)
    exposure = exec_w.sum(axis=1)

    m = metrics_from_returns(strat, bench, exposure, turnover)
    daily_df = pd.DataFrame(
        {
            "strategy_return": strat,
            "benchmark_return": bench,
            "gross_exposure": exposure,
            "equity": (1 + strat).cumprod(),
        }
    )
    return m, daily_df
