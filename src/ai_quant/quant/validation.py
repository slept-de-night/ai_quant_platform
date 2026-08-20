from __future__ import annotations

from copy import deepcopy
import statistics
from typing import List

from ..core.models import FoldResult, StrategySpec, ValidationReport
from .backtest import run_backtest


def walk_forward_validate(
    bars,
    spec: StrategySpec,
    train_days: int = 504,
    test_days: int = 126,
    step_days: int = 126,
    min_folds: int = 2,
    slippage_bps: float = 5,
    commission_bps: float = 0,
    min_sharpe: float = 0.5,
    max_drawdown: float = 0.25,
    min_robust: float = 0.2,
) -> ValidationReport:
    """Execute rigorous walk-forward out-of-sample cross-validation with stress & perturbation tests."""
    n = len(bars)
    folds: List[FoldResult] = []
    start = 0
    fold = 1

    while start + train_days + test_days <= n:
        train_start = bars.index[start]
        train_end = bars.index[start + train_days - 1]
        test_start = bars.index[start + train_days]
        test_end = bars.index[start + train_days + test_days - 1]

        warm_start = max(0, start + train_days - 260)
        chunk = bars.iloc[warm_start : start + train_days + test_days]
        m, _ = run_backtest(chunk, spec, slippage_bps, commission_bps, start=test_start, end=test_end)
        folds.append(
            FoldResult(
                fold=fold,
                train_start=str(train_start.date()),
                train_end=str(train_end.date()),
                test_start=str(test_start.date()),
                test_end=str(test_end.date()),
                metrics=m,
            )
        )
        fold += 1
        start += step_days

    if len(folds) < min_folds:
        raise ValueError(
            f"Only {len(folds)} walk-forward folds; need at least {min_folds}. Increase history or reduce window sizes."
        )

    sharpes = [x.metrics.sharpe for x in folds]
    returns = [x.metrics.total_return for x in folds]
    dds = [x.metrics.max_drawdown for x in folds]

    med = float(statistics.median(sharpes))
    worst = float(min(dds))
    pos = sum(r > 0 for r in returns) / len(returns)

    # Cost stress test: 3x slippage on recent out-of-sample window
    warm = max(0, n - test_days - 260)
    chunk = bars.iloc[warm:]
    stress, _ = run_backtest(chunk, spec, slippage_bps * 3, commission_bps, start=bars.index[-test_days])

    # Parameter perturbation robustness test
    p = deepcopy(spec)
    p.entry_threshold = min(0.95, spec.entry_threshold + 0.05)
    p.exit_threshold = max(-0.5, min(p.entry_threshold - 0.01, spec.exit_threshold - 0.02))
    perturb, _ = run_backtest(chunk, p, slippage_bps, commission_bps, start=bars.index[-test_days])

    robust = (
        0.45 * med
        + 0.20 * stress.sharpe
        + 0.15 * perturb.sharpe
        + 0.20 * (2 * pos - 1)
        - 0.5 * max(0, abs(worst) - max_drawdown)
    )

    # Deflated Sharpe Ratio (DSR) & PBO calculation
    # Bailey & López de Prado (2014)
    n_trials = max(1, len(folds) * 3)
    var_sharpe = float(statistics.variance(sharpes)) if len(sharpes) > 1 else 0.05
    euler_mascheroni = 0.5772156649
    # Expected maximum Sharpe under null hypothesis of no true alpha
    import math
    if n_trials > 1 and var_sharpe > 0:
        exp_max_sharpe = math.sqrt(var_sharpe) * (
            (1.0 - euler_mascheroni) * (2.0 * math.log(n_trials)) ** -0.5
            + (2.0 * math.log(n_trials)) ** 0.5
        )
    else:
        exp_max_sharpe = 0.0

    # Normal CDF approximation for DSR
    denom = math.sqrt(1.0 - 0.0 + (med ** 2) / (2.0 * len(bars))) if len(bars) > 0 else 1.0
    z_stat = (med - exp_max_sharpe) * math.sqrt(len(bars) / 252.0) / max(denom, 1e-6)
    dsr = float(0.5 * (1.0 + math.erf(z_stat / math.sqrt(2.0))))
    
    # Probability of Backtest Overfitting (PBO): fraction of negative out-of-sample folds
    pbo = float(sum(s <= 0 for s in sharpes) / len(sharpes))

    failures = []
    if med < min_sharpe:
        failures.append(f"median walk-forward Sharpe {med:.2f} < {min_sharpe:.2f}")
    if abs(worst) > max_drawdown:
        failures.append(f"worst drawdown {worst:.1%} exceeds {max_drawdown:.1%}")
    if pos < 0.5:
        failures.append(f"only {pos:.0%} of folds profitable")
    if stress.sharpe < 0:
        failures.append("cost-stress Sharpe is negative")
    if perturb.sharpe < 0:
        failures.append("small threshold perturbation collapses Sharpe below zero")
    if robust < min_robust:
        failures.append(f"robust score {robust:.2f} < {min_robust:.2f}")

    return ValidationReport(
        strategy_name=spec.name,
        folds=folds,
        median_sharpe=med,
        worst_drawdown=worst,
        positive_fold_ratio=pos,
        cost_stress_sharpe=stress.sharpe,
        perturbation_sharpe=perturb.sharpe,
        robust_score=float(robust),
        dsr=round(dsr, 4),
        pbo=round(pbo, 4),
        n_trials=n_trials,
        passed=not failures,
        failure_reasons=failures,
    )

