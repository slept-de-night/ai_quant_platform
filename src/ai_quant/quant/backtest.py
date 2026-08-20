from __future__ import annotations

from typing import Optional, Tuple
import numpy as np
import pandas as pd

from ..core.models import BacktestMetrics, StrategySpec
from ..data.features import feature_frame
from ..data.regime import regime_series
from .factors import compile_score


def _positions(score: pd.Series, features: pd.DataFrame, spec: StrategySpec) -> pd.Series:
    pos = []
    active = 0
    held = 0
    regimes = regime_series(features)
    allowed = {r.value for r in spec.regime_allow}

    for i, s in enumerate(score.fillna(0)):
        regime_ok = (not allowed) or (regimes.iloc[i] in allowed)
        if active == 0:
            if regime_ok and s >= spec.entry_threshold:
                active = 1
                held = 0
        else:
            held += 1
            if s <= spec.exit_threshold or held >= spec.max_holding_days or not regime_ok:
                active = 0
                held = 0
        pos.append(active)
    return pd.Series(pos, index=score.index, dtype=float)


def metrics_from_returns(
    strategy_ret: pd.Series,
    benchmark_ret: pd.Series,
    position: pd.Series,
    turnover: pd.Series,
) -> BacktestMetrics:
    """Calculate institutional backtest performance metrics."""
    s = strategy_ret.fillna(0)
    b = benchmark_ret.fillna(0)
    n = max(len(s), 1)

    eq = (1 + s).cumprod()
    total = float(eq.iloc[-1] - 1) if len(eq) else 0.0

    beq = (1 + b).cumprod()
    bench = float(beq.iloc[-1] - 1) if len(beq) else 0.0

    ann = float((1 + total) ** (252 / n) - 1) if total > -1 else -1.0
    vol = float(s.std(ddof=0) * np.sqrt(252))
    sharpe = float(s.mean() / s.std(ddof=0) * np.sqrt(252)) if s.std(ddof=0) > 1e-12 else 0.0

    neg = s[s < 0]
    downside = float(neg.std(ddof=0) * np.sqrt(252)) if len(neg) > 1 else 0.0
    sortino = float(s.mean() * 252 / downside) if downside > 1e-12 else 0.0

    peak = eq.cummax()
    dd = eq / peak - 1
    mdd = float(dd.min()) if len(dd) else 0.0
    calmar = float(ann / abs(mdd)) if mdd < 0 else 0.0

    cov = float(np.cov(s, b, ddof=0)[0, 1]) if len(s) > 1 else 0.0
    bvar = float(np.var(b))
    beta = cov / bvar if bvar > 1e-15 else 0.0
    alpha = float((s.mean() - beta * b.mean()) * 252)

    active = s - b
    ir = float(active.mean() / active.std(ddof=0) * np.sqrt(252)) if active.std(ddof=0) > 1e-12 else 0.0

    entries = position.diff().fillna(position) > 0
    invested = position > 0
    win = float((s[invested] > 0).mean()) if invested.any() else 0.0

    return BacktestMetrics(
        total_return=total,
        benchmark_return=bench,
        annualized_return=ann,
        annualized_vol=vol,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=mdd,
        calmar=calmar,
        beta=float(beta),
        alpha_annualized=alpha,
        information_ratio=ir,
        turnover=float(turnover.sum()),
        exposure=float(position.mean()),
        win_rate=win,
        trades=int(entries.sum()),
        observations=len(s),
    )


def run_backtest(
    bars: pd.DataFrame,
    spec: StrategySpec,
    slippage_bps: float = 5,
    commission_bps: float = 0,
    start: Optional[Any] = None,
    end: Optional[Any] = None,
) -> Tuple[BacktestMetrics, pd.DataFrame]:
    """Execute event-driven strategy simulation with realistic transaction friction."""
    f = feature_frame(bars).dropna().copy()
    if start is not None:
        f = f.loc[f.index >= start]
    if end is not None:
        f = f.loc[f.index <= end]
    if len(f) < 30:
        raise ValueError("Not enough observations after feature warmup/slicing")

    score = compile_score(f, spec)
    raw_pos = _positions(score, f, spec)
    position = raw_pos.shift(1).fillna(0)
    ret = f["close"].pct_change().fillna(0)
    turnover = position.diff().abs().fillna(position.abs())
    cost = turnover * ((slippage_bps + commission_bps) / 10000)
    strategy_ret = position * ret - cost

    m = metrics_from_returns(strategy_ret, ret, position, turnover)
    daily_df = pd.DataFrame(
        {
            "close": f["close"],
            "score": score,
            "position": position,
            "strategy_return": strategy_ret,
            "benchmark_return": ret,
            "equity": (1 + strategy_ret).cumprod(),
        },
        index=f.index,
    )
    return m, daily_df
