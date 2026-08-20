from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.features import feature_frame
from .models import Direction, TechnicalView


def _direction(score: float) -> Direction:
    if score >= 0.60:
        return Direction.STRONG_BULLISH
    if score >= 0.18:
        return Direction.BULLISH
    if score <= -0.60:
        return Direction.STRONG_BEARISH
    if score <= -0.18:
        return Direction.BEARISH
    return Direction.NEUTRAL


def analyze_technical(bars: pd.DataFrame) -> TechnicalView:
    """Deterministic quantitative technical indicator analysis."""
    f = feature_frame(bars).dropna()
    if f.empty:
        return TechnicalView(
            score=0,
            confidence=0,
            direction=Direction.UNKNOWN,
            trend="insufficient data",
            momentum="insufficient data",
            volatility="insufficient data",
            mean_reversion_risk="unknown",
            observations=[],
        )
    x = f.iloc[-1]
    trend = np.tanh(float(x["price_sma200"]) * 8) * 0.35 + np.tanh(float(x["sma20_sma50"]) * 16) * 0.25
    momentum = np.tanh(float(x["ret_20"]) * 7) * 0.25 + np.tanh(float(x["ret_5"]) * 10) * 0.15
    score = float(np.clip(trend + momentum, -1, 1))
    vol = float(x["vol_20"])
    rsi = float(x["rsi_14"]) * 50 + 50

    trend_text = "long-term uptrend" if x["price_sma200"] > 0 else "long-term downtrend"
    if x["sma20_sma50"] > 0:
        trend_text += ", short/medium trend aligned upward"
    else:
        trend_text += ", short/medium trend not aligned upward"

    mom_text = f"20-day return {x['ret_20']:+.1%}; 5-day return {x['ret_5']:+.1%}"
    vol_text = "elevated" if vol > 0.35 else "moderate" if vol > 0.18 else "low"
    mr = (
        "overbought risk elevated"
        if rsi >= 70
        else "oversold bounce risk elevated"
        if rsi <= 30
        else "no extreme RSI condition"
    )
    conf = 0.80 if len(f) >= 250 else 0.60

    return TechnicalView(
        score=score,
        confidence=conf,
        direction=_direction(score),
        trend=trend_text,
        momentum=mom_text,
        volatility=f"{vol_text} ({vol:.1%} annualized 20d)",
        mean_reversion_risk=mr,
        observations=[
            f"price vs SMA200: {x['price_sma200']:+.1%}",
            f"SMA20 vs SMA50: {x['sma20_sma50']:+.1%}",
            f"RSI14: {rsi:.1f}",
        ],
    )
