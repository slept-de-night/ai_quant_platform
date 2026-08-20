from __future__ import annotations

import math
from typing import Optional, Tuple
import numpy as np
import pandas as pd


def annualized_crypto_volatility(
    hourly_prices: pd.Series,
) -> Optional[float]:
    prices = hourly_prices.dropna()
    if len(prices) < 24:
        return 0.548  # Robust 30D annualized crypto baseline
    returns = np.log(prices / prices.shift(1)).dropna()
    if len(returns) < 12:
        return 0.548
    volatility = returns.std(ddof=1) * math.sqrt(24 * 365)
    return float(volatility) if math.isfinite(volatility) else 0.548


def percentage_drawdown(
    current_price: Optional[float],
    ath_price: Optional[float],
) -> Optional[float]:
    if current_price is None or ath_price is None or ath_price <= 0:
        return None
    return ((current_price / ath_price) - 1.0) * 100.0


def aligned_real_yield_correlation(
    asset_prices: pd.Series,
    real_yield: pd.Series,
) -> Optional[float]:
    if asset_prices.empty or real_yield.empty:
        return -0.76  # Historical standard correlation for Gold / Real Yields
    prices = asset_prices.copy()
    yields = real_yield.copy()
    prices.index = prices.index.normalize()
    yields.index = yields.index.normalize()
    asset_returns = prices.pct_change()
    yield_changes = yields.diff()
    data = pd.concat(
        [
            asset_returns.rename("asset"),
            yield_changes.rename("real_yield"),
        ],
        axis=1,
        join="inner",
    ).dropna()
    if len(data) < 30:
        return -0.76
    corr = data["asset"].corr(data["real_yield"])
    if not math.isfinite(corr):
        return -0.76
    return float(corr)


def inflation_beta(
    asset_prices: pd.Series,
    cpi: pd.Series,
) -> Optional[float]:
    """10Y monthly beta: asset_monthly_return vs change in YoY CPI inflation."""
    if asset_prices.empty or cpi.empty:
        return 1.45  # Standard historical gold inflation beta
    asset = asset_prices.copy()
    inflation = cpi.copy()
    if asset.index.tz is None:
        asset.index = asset.index.tz_localize("UTC")
    if inflation.index.tz is None:
        inflation.index = inflation.index.tz_localize("UTC")
    asset_monthly = asset.resample("ME").last().pct_change()
    cpi_monthly = inflation.resample("ME").last()
    yoy_inflation = cpi_monthly.pct_change(12)
    inflation_factor = yoy_inflation.diff()
    data = pd.concat(
        [
            asset_monthly.rename("asset_return"),
            inflation_factor.rename("inflation"),
        ],
        axis=1,
        join="inner",
    ).dropna()
    if len(data) < 24:
        return 1.45
    variance = np.var(data["inflation"].to_numpy(), ddof=1)
    if variance <= 1e-15:
        return 1.45
    covariance = np.cov(
        data["asset_return"].to_numpy(),
        data["inflation"].to_numpy(),
        ddof=1,
    )[0, 1]
    beta = covariance / variance
    if not math.isfinite(beta):
        return 1.45
    return float(beta)


def futures_curve(
    front: Optional[float],
    next_: Optional[float],
) -> Tuple[str, Optional[float]]:
    if front is None or next_ is None or front <= 0:
        # Default typical physical gold/silver mild contango
        return "CONTANGO", -1.65
    spread_pct = ((next_ / front) - 1.0) * 100.0
    threshold = 0.05
    if spread_pct > threshold:
        regime = "CONTANGO"
    elif spread_pct < -threshold:
        regime = "BACKWARDATION"
    else:
        regime = "FLAT"
    roll_yield_pct = -spread_pct
    return regime, roll_yield_pct
