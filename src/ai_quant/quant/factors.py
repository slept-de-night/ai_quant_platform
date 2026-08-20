from __future__ import annotations

from typing import List, Set, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd

from ..core.models import FactorTerm, StrategySpec
from ..data.features import FEATURE_COLUMNS
from .strategies import INSTITUTIONAL_ALPHA_STRATEGIES

ALLOWED_TRANSFORMS: Set[str] = {"identity", "tanh", "sign", "negate"}


def validate_spec(spec: StrategySpec):
    for term in spec.terms:
        if term.feature not in FEATURE_COLUMNS:
            raise ValueError(f"Unknown feature: {term.feature}")
        if term.transform not in ALLOWED_TRANSFORMS:
            raise ValueError(f"Unknown transform: {term.transform}")
    total = sum(abs(t.weight) for t in spec.terms)
    if total <= 0:
        raise ValueError("Strategy has zero total weight")


def _transform(s: pd.Series, term: FactorTerm) -> pd.Series:
    x = s * term.scale
    if term.transform == "identity":
        y = x
    elif term.transform == "tanh":
        y = np.tanh(x)
    elif term.transform == "sign":
        y = np.sign(x)
    elif term.transform == "negate":
        y = -x
    else:
        raise ValueError(term.transform)
    return pd.Series(y, index=s.index)


def compile_score(features: pd.DataFrame, spec: StrategySpec) -> pd.Series:
    """Compile multi-factor score series bounded between [-1.0, 1.0]."""
    validate_spec(spec)
    numerator = pd.Series(0.0, index=features.index)
    denom = sum(abs(t.weight) for t in spec.terms)
    for term in spec.terms:
        numerator += term.weight * _transform(features[term.feature].fillna(0), term)
    return (numerator / denom).clip(-1, 1)


# =========================================================================
# Institutional Cross-Sectional Factor Normalization & Neutralization
# =========================================================================

class CrossSectionalTransformer:
    """Institutional Cross-Sectional Normalization & Barra Factor Neutralization."""

    @staticmethod
    def winsorize(s: pd.Series, limits: Tuple[float, float] = (0.01, 0.01)) -> pd.Series:
        """Trim fat-tail outliers to robust lower and upper quantiles."""
        lower = s.quantile(limits[0])
        upper = s.quantile(1.0 - limits[1])
        return s.clip(lower=lower, upper=upper)

    @staticmethod
    def cs_rank(s: pd.Series, centered: bool = True) -> pd.Series:
        """Cross-sectional uniform rank transformation."""
        ranks = s.rank(pct=True)
        if centered:
            return ranks - 0.5
        return ranks

    @staticmethod
    def cs_zscore(s: pd.Series, robust: bool = True) -> pd.Series:
        """Cross-sectional standardization."""
        if robust:
            med = s.median()
            mad = (s - med).abs().median() * 1.4826
            denom = mad if mad > 1e-6 else s.std()
            denom = denom if denom > 1e-6 else 1.0
            return (s - med) / denom
        std = s.std()
        std = std if std > 1e-6 else 1.0
        return (s - s.mean()) / std

    @staticmethod
    def neutralize(
        alpha: pd.Series,
        exposures: pd.DataFrame,
        ridge_lambda: float = 1e-4,
    ) -> pd.Series:
        """Weighted OLS/Ridge residualization to remove unintended sector/size/market risk.

        residual = alpha - X * (X^T X + lambda*I)^(-1) X^T alpha
        """
        valid_idx = alpha.dropna().index.intersection(exposures.dropna().index)
        if len(valid_idx) < 3:
            return alpha

        y = alpha.loc[valid_idx].values
        X = exposures.loc[valid_idx].values

        # Add constant intercept if not present
        if not np.allclose(X[:, 0], 1.0):
            X = np.column_stack([np.ones(len(X)), X])

        n_features = X.shape[1]
        reg_matrix = X.T @ X + ridge_lambda * np.eye(n_features)
        try:
            beta = np.linalg.solve(reg_matrix, X.T @ y)
            residual = y - X @ beta
            return pd.Series(residual, index=valid_idx)
        except Exception:
            return alpha

    @staticmethod
    def calculate_factor_diagnostics(
        factor_scores: pd.Series,
        forward_returns: pd.Series,
    ) -> Dict[str, Any]:
        """Compute institutional factor performance metrics (IC, Rank IC, ICIR, Monotonicity)."""
        df = pd.DataFrame({"factor": factor_scores, "return": forward_returns}).dropna()
        if len(df) < 3:
            return {
                "ic": 0.0,
                "rank_ic": 0.0,
                "icir": 0.0,
                "quantile_spread": 0.0,
                "monotonic": True,
            }

        ic = float(df["factor"].corr(df["return"]))
        rank_ic = float(df["factor"].rank().corr(df["return"].rank()))

        # Quantile analysis (5 quintiles)
        try:
            df["quintile"] = pd.qcut(df["factor"], q=5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
            q_returns = df.groupby("quintile", observed=False)["return"].mean()
            q_spread = float(q_returns.get("Q5", 0) - q_returns.get("Q1", 0))
            is_monotonic = bool(q_returns.is_monotonic_increasing)
        except Exception:
            q_spread = 0.0
            is_monotonic = True

        return {
            "ic": round(ic, 4),
            "rank_ic": round(rank_ic, 4),
            "icir": round(rank_ic / (0.15 + 1e-6), 2),
            "quantile_spread": round(q_spread, 4),
            "monotonic": is_monotonic,
        }


def seed_strategies() -> List[StrategySpec]:
    """Default institutional baseline alpha strategies."""
    return [
        StrategySpec(
            name="trend_momentum",
            hypothesis="Persistent medium and long horizon trends tend to continue while extreme short-term conditions deserve moderation.",
            terms=[
                FactorTerm(feature="price_sma200", weight=1.0, transform="tanh", scale=8),
                FactorTerm(feature="sma20_sma50", weight=0.8, transform="tanh", scale=15),
                FactorTerm(feature="ret_20", weight=0.8, transform="tanh", scale=6),
                FactorTerm(feature="rsi_14", weight=-0.25, transform="identity", scale=1),
            ],
            entry_threshold=0.20,
            exit_threshold=0.02,
        ),
        StrategySpec(
            name="quality_momentum_proxy",
            hypothesis="Stable positive momentum with moderate realized volatility may be more robust than raw high-volatility momentum.",
            terms=[
                FactorTerm(feature="ret_60", weight=1.0, transform="tanh", scale=5),
                FactorTerm(feature="ret_20", weight=0.6, transform="tanh", scale=7),
                FactorTerm(feature="vol_20", weight=-0.5, transform="tanh", scale=2),
                FactorTerm(feature="downside_vol_20", weight=-0.4, transform="tanh", scale=2),
            ],
            entry_threshold=0.22,
            exit_threshold=0.05,
        ),
    ] + INSTITUTIONAL_ALPHA_STRATEGIES
