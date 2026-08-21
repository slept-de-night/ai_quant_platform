from __future__ import annotations

from typing import List
import numpy as np
import pandas as pd

FEATURE_COLUMNS: List[str] = [
    "ret_1",
    "ret_5",
    "ret_20",
    "ret_60",
    "vol_20",
    "vol_60",
    "downside_vol_20",
    "volume_z_20",
    "atr_14",
    "atr_pct_14",
    "rsi_14",
    "sma_20",
    "sma_50",
    "sma_200",
    "price_sma200",
    "sma20_sma50",
    "macd",
    "macd_signal",
]


def feature_frame(bars: pd.DataFrame) -> pd.DataFrame:
    """Compute rich quantitative features from OHLCV market bars."""
    df = bars.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # Returns
    df["ret_1"] = close.pct_change(1)
    df["ret_5"] = close.pct_change(5)
    df["ret_20"] = close.pct_change(20)
    df["ret_60"] = close.pct_change(60)

    # Realized Volatility (annualized)
    df["vol_20"] = df["ret_1"].rolling(20).std() * np.sqrt(252)
    df["vol_60"] = df["ret_1"].rolling(60).std() * np.sqrt(252)

    # Downside Volatility
    downside_ret = df["ret_1"].apply(lambda x: x if x < 0 else 0.0)
    df["downside_vol_20"] = downside_ret.rolling(20).std() * np.sqrt(252)

    # Volume Z-score
    vol_mean = volume.rolling(20).mean()
    vol_std = volume.rolling(20).std().replace(0, 1.0)
    df["volume_z_20"] = (volume - vol_mean) / vol_std

    # ATR 14
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr_14"] = tr.rolling(14).mean()
    df["atr_pct_14"] = df["atr_14"] / close

    # RSI 14
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean().replace(0, 1e-9)
    rs = avg_gain / avg_loss
    df["rsi_14"] = 100 - (100 / (1 + rs))

    # Moving averages
    df["sma_20"] = close.rolling(20).mean()
    df["sma_50"] = close.rolling(50).mean()
    df["sma_200"] = close.rolling(200).mean()

    # Ratios
    df["price_sma200"] = (close / df["sma_200"].replace(0, np.nan)) - 1.0
    df["sma20_sma50"] = (df["sma_20"] / df["sma_50"].replace(0, np.nan)) - 1.0

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    return df
