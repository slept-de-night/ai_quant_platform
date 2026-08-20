from __future__ import annotations

from typing import List, Dict, Any
from ..core.models import StrategySpec, FactorTerm, Regime

INSTITUTIONAL_ALPHA_STRATEGIES: List[StrategySpec] = [
    StrategySpec(
        name="vol_adjusted_cross_sectional_momentum",
        hypothesis=(
            "Securities with persistent medium/long-horizon positive returns "
            "continue outperforming, but momentum quality deteriorates as "
            "realized and downside volatility increase."
        ),
        terms=[
            FactorTerm(feature="ret_20", weight=0.34, transform="tanh", scale=8.0),
            FactorTerm(feature="ret_60", weight=0.32, transform="tanh", scale=5.0),
            FactorTerm(feature="ret_5", weight=0.10, transform="tanh", scale=14.0),
            FactorTerm(feature="vol_20", weight=-0.12, transform="tanh", scale=30.0),
            FactorTerm(feature="downside_vol_20", weight=-0.12, transform="tanh", scale=35.0),
        ],
        entry_threshold=0.18,
        exit_threshold=0.05,
        max_holding_days=35,
        regime_allow=[
            Regime.BULL_LOW_VOL,
            Regime.BULL_HIGH_VOL,
            Regime.BEAR_LOW_VOL,
        ],
    ),
    StrategySpec(
        name="mean_reversion_volume_exhaustion",
        hypothesis=(
            "Sharp short-horizon declines accompanied by abnormal volume and "
            "elevated downside volatility frequently represent temporary "
            "liquidity exhaustion rather than persistent information shocks."
        ),
        terms=[
            FactorTerm(feature="ret_1", weight=-0.40, transform="tanh", scale=25.0),
            FactorTerm(feature="ret_5", weight=-0.28, transform="tanh", scale=14.0),
            FactorTerm(feature="volume_z_20", weight=0.22, transform="tanh", scale=0.70),
            FactorTerm(feature="downside_vol_20", weight=0.10, transform="tanh", scale=30.0),
            FactorTerm(feature="vol_20", weight=-0.06, transform="tanh", scale=30.0),
        ],
        entry_threshold=0.16,
        exit_threshold=0.03,
        max_holding_days=5,
        regime_allow=[
            Regime.BULL_LOW_VOL,
            Regime.BULL_HIGH_VOL,
            Regime.BEAR_LOW_VOL,
        ],
    ),
    StrategySpec(
        name="multi_horizon_trend_breakout",
        hypothesis=(
            "Breakouts confirmed simultaneously across short, intermediate, "
            "and long horizons and supported by abnormal trading volume are "
            "more persistent than isolated short-term price moves."
        ),
        terms=[
            FactorTerm(feature="ret_5", weight=0.20, transform="tanh", scale=16.0),
            FactorTerm(feature="ret_20", weight=0.28, transform="tanh", scale=9.0),
            FactorTerm(feature="ret_60", weight=0.26, transform="tanh", scale=5.0),
            FactorTerm(feature="volume_z_20", weight=0.14, transform="tanh", scale=0.60),
            FactorTerm(feature="atr_pct_14", weight=0.08, transform="tanh", scale=20.0),
            FactorTerm(feature="vol_20", weight=-0.10, transform="tanh", scale=25.0),
        ],
        entry_threshold=0.22,
        exit_threshold=0.07,
        max_holding_days=45,
        regime_allow=[
            Regime.BULL_LOW_VOL,
            Regime.BULL_HIGH_VOL,
            Regime.BEAR_LOW_VOL,
        ],
    ),
]
