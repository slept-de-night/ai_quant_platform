from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from .clock import QuantClock
from .snapshot import QuantSnapshot
from ..core.models import PortfolioState


class RuntimeMode(str, Enum):
    BACKTEST = "backtest"
    REPLAY = "replay"
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True)
class DecisionContext:
    """Unified execution and decision context provided to alpha strategies.
    
    Attributes:
        run_id: Unique batch/execution run identifier.
        decision_id: Unique identifier for this discrete strategy decision.
        trace_id: Distributed trace ID across the entire decision lifecycle.
        mode: Execution mode (BACKTEST, REPLAY, PAPER, LIVE).
        clock: Time provider.
        snapshot: Cryptographically immutable market and fundamental data snapshot.
        portfolio: Current portfolio state (cash, positions, daily PnL).
        strategy_version: Version identifier of the strategy being evaluated.
        parameters: Strategy hyperparameter configuration.
    """
    run_id: str
    decision_id: str
    trace_id: str
    mode: RuntimeMode
    clock: QuantClock
    snapshot: QuantSnapshot
    portfolio: PortfolioState
    strategy_version: str = "v1.0"
    parameters: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        mode: RuntimeMode,
        clock: QuantClock,
        snapshot: QuantSnapshot,
        portfolio: PortfolioState,
        strategy_version: str = "v1.0",
        run_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> DecisionContext:
        return cls(
            run_id=run_id or uuid.uuid4().hex,
            decision_id=uuid.uuid4().hex,
            trace_id=trace_id or uuid.uuid4().hex,
            mode=mode,
            clock=clock,
            snapshot=snapshot,
            portfolio=portfolio,
            strategy_version=strategy_version,
            parameters=parameters or {},
        )
