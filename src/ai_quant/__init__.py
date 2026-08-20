from __future__ import annotations

__version__ = "1.2.0"

# Feature Subpackages
from . import core
from . import data
from . import quant
from . import intelligence
from . import runtime
from . import execution
from . import api

# Root Convenience Exports
from .core.config import Settings, settings
from .core.models import (
    Side,
    Regime,
    StrategyStatus,
    FactorTerm,
    StrategySpec,
    BacktestMetrics,
    FoldResult,
    ValidationReport,
    ResearchCandidate,
    CandidateBatch,
    Signal,
    OrderIntent,
    PortfolioState,
    RiskDecision,
)
from .core.registry import Registry
from .quant.factors import seed_strategies, compile_score, validate_spec
from .quant.backtest import run_backtest, metrics_from_returns
from .quant.validation import walk_forward_validate
from .quant.portfolio import portfolio_backtest
from .quant.alpha_factory import AlphaFactory
from .intelligence.engine import IntelligenceEngine
from .intelligence.agent_memory import AgentMemoryStore, MemoryKind, MemoryNote
from .intelligence.memory_maintenance import MemoryMaintenance
from .runtime.orchestrator import TaskOrchestrator, TaskRuntime, WorkerPool
from .runtime.router import ModelRouter, RouteRequest, ModelDecision
from .runtime.deployment import ModelControlPlane, DeploymentStatus
from .runtime.evaluation import EvaluationManager, TaskEvaluation
from .execution.risk import RiskEngine, calculate_institutional_risk_profile
from .execution.engine import PaperTradingEngine
from .execution.broker import AlpacaPaperBroker
from .execution.go_client import GoEngineClient

__all__ = [
    "__version__",
    "core",
    "data",
    "quant",
    "intelligence",
    "runtime",
    "execution",
    "api",
    "Settings",
    "settings",
    "Side",
    "Regime",
    "StrategyStatus",
    "FactorTerm",
    "StrategySpec",
    "BacktestMetrics",
    "FoldResult",
    "ValidationReport",
    "ResearchCandidate",
    "CandidateBatch",
    "Signal",
    "OrderIntent",
    "PortfolioState",
    "RiskDecision",
    "Registry",
    "seed_strategies",
    "compile_score",
    "validate_spec",
    "run_backtest",
    "metrics_from_returns",
    "walk_forward_validate",
    "portfolio_backtest",
    "AlphaFactory",
    "IntelligenceEngine",
    "AgentMemoryStore",
    "MemoryKind",
    "MemoryNote",
    "MemoryMaintenance",
    "TaskOrchestrator",
    "TaskRuntime",
    "WorkerPool",
    "ModelRouter",
    "RouteRequest",
    "ModelDecision",
    "ModelControlPlane",
    "DeploymentStatus",
    "EvaluationManager",
    "TaskEvaluation",
    "RiskEngine",
    "calculate_institutional_risk_profile",
    "PaperTradingEngine",
    "AlpacaPaperBroker",
    "GoEngineClient",
]
