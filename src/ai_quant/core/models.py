from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class StrategyStatus(str, Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    APPROVED = "approved"
    RETIRED = "retired"


class Regime(str, Enum):
    BULL_LOW_VOL = "bull_low_vol"
    BULL_HIGH_VOL = "bull_high_vol"
    BEAR_LOW_VOL = "bear_low_vol"
    BEAR_HIGH_VOL = "bear_high_vol"
    UNKNOWN = "unknown"


class FactorTerm(BaseModel):
    feature: str
    weight: float = Field(ge=-2.0, le=2.0)
    transform: str = Field(default="tanh")
    scale: float = Field(default=1.0, gt=0.0, le=50.0)


class StrategySpec(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    hypothesis: str = Field(min_length=10, max_length=1000)
    terms: List[FactorTerm] = Field(min_length=1, max_length=10)
    entry_threshold: float = Field(default=0.25, ge=0.05, le=0.95)
    exit_threshold: float = Field(default=0.05, ge=-0.50, le=0.50)
    regime_allow: List[Regime] = Field(default_factory=list)
    max_holding_days: int = Field(default=60, ge=1, le=252)

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.exit_threshold >= self.entry_threshold:
            raise ValueError("exit_threshold must be below entry_threshold")
        return self


class BacktestMetrics(BaseModel):
    total_return: float
    benchmark_return: float
    annualized_return: float
    annualized_vol: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    beta: float
    alpha_annualized: float
    information_ratio: float
    turnover: float
    exposure: float
    win_rate: float
    trades: int
    observations: int


class FoldResult(BaseModel):
    fold: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    metrics: BacktestMetrics


class ValidationReport(BaseModel):
    strategy_name: str
    folds: List[FoldResult]
    median_sharpe: float
    worst_drawdown: float
    positive_fold_ratio: float
    cost_stress_sharpe: float
    perturbation_sharpe: float
    robust_score: float
    dsr: Optional[float] = None  # Deflated Sharpe Ratio
    pbo: Optional[float] = None  # Probability of Backtest Overfitting
    n_trials: Optional[int] = None
    passed: bool
    failure_reasons: List[str] = Field(default_factory=list)



class ResearchCandidate(BaseModel):
    strategy: StrategySpec
    why_different: str = Field(min_length=5, max_length=500)
    failure_modes: List[str] = Field(default_factory=list, max_length=8)


class CandidateBatch(BaseModel):
    candidates: List[ResearchCandidate] = Field(min_length=1, max_length=12)


class PortfolioState(BaseModel):
    equity: float
    cash: float
    gross_exposure: float
    daily_pnl: float
    peak_equity: float
    current_symbol_exposure: float = 0.0
    current_symbol_qty: float = 0.0
    orders_today: int = 0
    is_frozen: bool = False


class Signal(BaseModel):
    symbol: str
    strategy_name: str
    score: float = Field(ge=-1.0, le=1.0)
    side: Side
    reference_price: float
    regime: Regime
    reason: str
    context_multiplier: float = Field(default=1.0, ge=0.0, le=1.05)
    context_trust: float = Field(default=1.0, ge=0.0, le=1.0)
    trace_id: Optional[str] = None
    dataset_version: Optional[str] = None


class OrderIntent(BaseModel):
    symbol: str
    strategy_name: str
    side: Side
    qty: int
    reference_price: float
    notional: float
    client_order_id: str
    reason: str
    trace_id: Optional[str] = None
    dataset_version: Optional[str] = None


class RiskDecision(BaseModel):
    approved: bool
    order: Optional[OrderIntent] = None
    reasons: List[str] = Field(default_factory=list)
    trace_id: Optional[str] = None
    is_frozen: bool = False



__all__ = [
    "Side",
    "StrategyStatus",
    "Regime",
    "FactorTerm",
    "StrategySpec",
    "BacktestMetrics",
    "FoldResult",
    "ValidationReport",
    "ResearchCandidate",
    "CandidateBatch",
    "PortfolioState",
    "Signal",
    "OrderIntent",
    "RiskDecision",
]
