from __future__ import annotations

import logging
from typing import Optional
import numpy as np
import pandas as pd
import httpx

logger = logging.getLogger(__name__)


def synthetic_bars(symbol: str, days: int = 600) -> pd.DataFrame:
    """Generate deterministic synthetic daily bars for a given symbol."""
    seed = sum(ord(c) for c in symbol) % (2**31 - 1)
    rng = np.random.default_rng(seed)

    dates = pd.date_range(end=pd.Timestamp.now().normalize(), periods=days, freq="B")

    dt = 1.0 / 252.0
    mu = 0.08
    sigma = 0.20

    p0 = 100.0 + float(seed % 150)
    returns = rng.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt), size=days)
    close = p0 * np.exp(np.cumsum(returns))

    open_p = close * (1 + rng.normal(0, 0.003, size=days))
    high = np.maximum(open_p, close) * (1 + np.abs(rng.normal(0, 0.006, size=days)))
    low = np.minimum(open_p, close) * (1 - np.abs(rng.normal(0, 0.006, size=days)))
    volume = rng.integers(100000, 5000000, size=days).astype(float)

    df = pd.DataFrame(
        {
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "returns": returns,
        },
        index=dates,
    )
    df.index.name = "date"
    df["date"] = dates
    return df


def validate_bars(df: pd.DataFrame) -> pd.DataFrame:
    """Validate DataFrame contains required OHLCV columns and is well-formed."""
    if df is None or df.empty:
        raise ValueError("DataFrame is empty")
    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    return df.dropna(subset=["close"])


def alpaca_daily_bars(
    symbol: str,
    days: int = 900,
    api_key: str = "",
    secret_key: str = "",
) -> pd.DataFrame:
    """Fetch daily bars from Alpaca Market Data API or fall back to synthetic."""
    if not api_key or not secret_key:
        return synthetic_bars(symbol, days)

    try:
        url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
        headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
        }
        params = {
            "timeframe": "1Day",
            "limit": min(days, 1000),
            "adjustment": "all",
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                data = resp.json()
                bars = data.get("bars", [])
                if bars:
                    df = pd.DataFrame(bars)
                    df = df.rename(
                        columns={
                            "t": "date",
                            "o": "open",
                            "h": "high",
                            "l": "low",
                            "c": "close",
                            "v": "volume",
                        }
                    )
                    df["date"] = pd.to_datetime(df["date"])
                    df.set_index("date", inplace=True)
                    df["returns"] = df["close"].pct_change().fillna(0.0)
                    return df
    except Exception as exc:
        logger.warning(f"Failed to fetch Alpaca bars for {symbol}: {exc}")

    return synthetic_bars(symbol, days)


def get_market_bars(
    symbol: str,
    days: int = 1600,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    use_alpaca: bool = False,
) -> pd.DataFrame:
    """Fetch market bars for research and backtesting."""
    if use_alpaca and api_key and secret_key:
        return alpaca_daily_bars(symbol, days, api_key, secret_key)
    return synthetic_bars(symbol, days)
