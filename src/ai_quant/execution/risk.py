from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
import numpy as np

from ..core.config import Settings
from ..core.models import OrderIntent, PortfolioState, RiskDecision, Side, Signal


def calculate_parametric_var(
    returns: Union[np.ndarray, List[float]],
    equity: float,
    confidence: float = 0.95,
) -> float:
    """Calculate 1-day Parametric Value-at-Risk (USD)."""
    if len(returns) < 5 or equity <= 0:
        return 0.0
    arr = np.array(returns, dtype=float)
    mean = np.mean(arr)
    std = np.std(arr, ddof=1)
    # Z-scores: 0.95 -> 1.645, 0.99 -> 2.326
    z = 1.645 if confidence <= 0.95 else 2.326
    var_pct = max(0.0, -(mean - z * std))
    return float(round(var_pct * equity, 2))


def calculate_historical_var(
    returns: Union[np.ndarray, List[float]],
    equity: float,
    confidence: float = 0.95,
) -> float:
    """Calculate 1-day Historical Value-at-Risk (USD)."""
    if len(returns) < 5 or equity <= 0:
        return 0.0
    arr = np.array(returns, dtype=float)
    cutoff = (1.0 - confidence) * 100.0
    percentile_ret = np.percentile(arr, cutoff)
    var_pct = max(0.0, -percentile_ret)
    return float(round(var_pct * equity, 2))


def calculate_cvar(
    returns: Union[np.ndarray, List[float]],
    equity: float,
    confidence: float = 0.95,
) -> float:
    """Calculate 1-day Conditional Value-at-Risk / Expected Shortfall (USD)."""
    if len(returns) < 5 or equity <= 0:
        return 0.0
    arr = np.array(returns, dtype=float)
    cutoff = (1.0 - confidence) * 100.0
    var_threshold = np.percentile(arr, cutoff)
    tail_losses = arr[arr <= var_threshold]
    if len(tail_losses) == 0:
        return float(round(max(0.0, -var_threshold) * equity, 2))
    cvar_pct = max(0.0, -np.mean(tail_losses))
    return float(round(cvar_pct * equity, 2))


def calculate_institutional_risk_profile(
    returns: Union[np.ndarray, List[float]],
    equity: float = 100000.0,
    benchmark_returns: Optional[Union[np.ndarray, List[float]]] = None,
) -> Dict[str, Any]:
    """Compute comprehensive institutional risk metrics."""
    if len(returns) < 5:
        return {
            "equity": equity,
            "var_95_usd": 0.0,
            "var_99_usd": 0.0,
            "cvar_95_usd": 0.0,
            "annualized_volatility": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "beta": 1.0,
        }

    arr = np.array(returns, dtype=float)
    mean_daily = np.mean(arr)
    std_daily = np.std(arr, ddof=1) if len(arr) > 1 else 0.0
    ann_vol = std_daily * math.sqrt(252)

    neg_returns = arr[arr < 0]
    downside_std = np.std(neg_returns, ddof=1) if len(neg_returns) > 1 else 1e-6
    ann_downside = downside_std * math.sqrt(252)

    sharpe = (mean_daily * 252) / (ann_vol + 1e-6)
    sortino = (mean_daily * 252) / (ann_downside + 1e-6)

    cum_returns = np.cumprod(1 + arr)
    peak = np.maximum.accumulate(cum_returns)
    drawdowns = (peak - cum_returns) / (peak + 1e-9)
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
    annualized_return = (cum_returns[-1] ** (252.0 / len(arr))) - 1.0 if cum_returns[-1] > 0 else -1.0
    calmar = annualized_return / (max_dd + 1e-6)

    beta = 1.0
    if benchmark_returns is not None and len(benchmark_returns) == len(arr):
        bm_arr = np.array(benchmark_returns, dtype=float)
        cov = np.cov(arr, bm_arr)[0, 1]
        bm_var = np.var(bm_arr, ddof=1)
        if bm_var > 1e-8:
            beta = float(cov / bm_var)

    var_95 = calculate_parametric_var(arr, equity, 0.95)
    var_99 = calculate_parametric_var(arr, equity, 0.99)
    cvar_95 = calculate_cvar(arr, equity, 0.95)

    return {
        "equity": equity,
        "var_95_usd": var_95,
        "var_99_usd": var_99,
        "cvar_95_usd": cvar_95,
        "annualized_return": round(float(annualized_return), 4),
        "annualized_volatility": round(float(ann_vol), 4),
        "max_drawdown": round(float(max_dd), 4),
        "sharpe_ratio": round(float(sharpe), 2),
        "sortino_ratio": round(float(sortino), 2),
        "calmar_ratio": round(float(calmar), 2),
        "beta": round(float(beta), 2),
    }


class RiskEngine:
    """Hard Pre-Trade Risk Engine."""

    def __init__(self, cfg: Settings):
        self.cfg = cfg

    def evaluate(self, signal: Signal, p: PortfolioState) -> RiskDecision:
        fail = []
        if p.equity <= 0 or signal.reference_price <= 0:
            fail.append("invalid account equity or price")
        if p.orders_today >= self.cfg.max_orders_per_day:
            fail.append("daily order-count limit reached")
        if p.equity > 0 and (-p.daily_pnl / p.equity) >= self.cfg.max_daily_loss_pct:
            fail.append("daily-loss kill switch active")
        dd = (p.peak_equity - p.equity) / p.peak_equity if p.peak_equity > 0 else 0
        if dd >= self.cfg.max_drawdown_pct:
            fail.append("portfolio drawdown kill switch active")
        if fail:
            return RiskDecision(approved=False, reasons=fail)
        if signal.side == Side.HOLD:
            return RiskDecision(approved=False, reasons=["signal is HOLD"])
        if signal.side == Side.SELL:
            if p.current_symbol_qty <= 0:
                return RiskDecision(approved=False, reasons=["long-only mode: no position exists to sell"])
            qty = int(math.floor(p.current_symbol_qty))
            if qty < 1:
                return RiskDecision(approved=False, reasons=["position is below one whole share"])
        else:
            max_symbol = p.equity * self.cfg.max_position_pct
            symbol_capacity = max(0.0, max_symbol - p.current_symbol_exposure)
            gross_capacity = max(0.0, p.equity * self.cfg.max_gross_exposure_pct - p.gross_exposure)
            reserve = p.equity * self.cfg.min_cash_reserve_pct
            cash_capacity = max(0.0, p.cash - reserve)
            target = min(symbol_capacity, gross_capacity, cash_capacity, max_symbol * max(0.25, abs(signal.score)))
            target *= signal.context_multiplier
            qty = int(target / signal.reference_price)
            if qty < 1 or qty * signal.reference_price < self.cfg.min_order_notional:
                return RiskDecision(approved=False, reasons=["risk-sized order is too small"])

        seed = f"{datetime.now(timezone.utc).date()}|{signal.symbol}|{signal.strategy_name}|{signal.side.value}"
        cid = "aq-" + hashlib.sha256(seed.encode()).hexdigest()[:24]
        order = OrderIntent(
            symbol=signal.symbol,
            strategy_name=signal.strategy_name,
            side=signal.side,
            qty=qty,
            reference_price=signal.reference_price,
            notional=qty * signal.reference_price,
            client_order_id=cid,
            reason=signal.reason,
        )
        return RiskDecision(approved=True, order=order, reasons=["all hard risk gates passed"])
