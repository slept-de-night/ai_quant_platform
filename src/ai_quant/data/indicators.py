from __future__ import annotations

from typing import Any, Dict
import pandas as pd
from .features import feature_frame


def compute_technical_indicators(bars: pd.DataFrame) -> Dict[str, Any]:
    """Compute summary technical indicators from OHLCV bars."""
    f = feature_frame(bars).dropna()
    if f.empty:
        return {}
    latest = f.iloc[-1]
    return {
        "rsi_14": float(latest.get("rsi_14", 50.0)),
        "sma_20": float(latest.get("sma_20", latest["close"])),
        "sma_50": float(latest.get("sma_50", latest["close"])),
        "sma_200": float(latest.get("sma_200", latest["close"])),
        "vol_20": float(latest.get("vol_20", 0.20)),
        "atr_14": float(latest.get("atr_14", 1.0)),
        "macd": float(latest.get("macd", 0.0)),
        "macd_signal": float(latest.get("macd_signal", 0.0)),
    }
