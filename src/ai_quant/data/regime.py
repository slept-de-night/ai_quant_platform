from __future__ import annotations

import numpy as np
import pandas as pd
from ..core.models import Regime


def regime_series(features: pd.DataFrame) -> pd.Series:
    """Classify historical market regimes (Bull/Bear x Low/High Volatility)."""
    df = features
    if "ret_60" in df.columns:
        trend = df["ret_60"].fillna(0)
    elif "ret_20" in df.columns:
        trend = df["ret_20"].fillna(0)
    else:
        trend = pd.Series(0.0, index=df.index)

    if "vol_20" in df.columns:
        vol = df["vol_20"].fillna(0.18)
    elif "ret_1" in df.columns:
        vol = df["ret_1"].rolling(20).std().fillna(0.01) * np.sqrt(252)
    else:
        vol = pd.Series(0.18, index=df.index)

    vol_median = vol.rolling(100, min_periods=20).median().fillna(0.20)

    regimes = []
    for t_val, v_val, v_med in zip(trend, vol, vol_median):
        is_bull = t_val >= 0.0
        is_high_vol = v_val > v_med
        if is_bull:
            regimes.append(Regime.BULL_HIGH_VOL.value if is_high_vol else Regime.BULL_LOW_VOL.value)
        else:
            regimes.append(Regime.BEAR_HIGH_VOL.value if is_high_vol else Regime.BEAR_LOW_VOL.value)

    return pd.Series(regimes, index=df.index)


def latest_regime(features: pd.DataFrame) -> Regime:
    """Get the latest regime classification."""
    s = regime_series(features)
    if s.empty:
        return Regime.UNKNOWN
    return Regime(s.iloc[-1])
