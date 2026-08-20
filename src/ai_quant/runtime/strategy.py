from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .context import DecisionContext
from ..core.models import Side


@dataclass(frozen=True)
class StrategyDecision:
    """Output decision produced by a Strategy.evaluate(context).
    
    Attributes:
        symbol: Target ticker symbol.
        side: Decision direction (BUY, SELL, HOLD).
        target_weight: Target portfolio weight (-1.0 to +1.0).
        target_qty: Target quantity in shares/units.
        confidence: Strategy confidence score (0.0 to 1.0).
        reasons: List of explanatory signals / factor triggers.
        metadata: Additional diagnostic indicators.
    """
    symbol: str
    side: Side
    target_weight: float
    target_qty: Optional[int] = None
    confidence: float = 1.0
    reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class StrategyProtocol(Protocol):
    """Canonical Strategy Interface adhering to strict dependency inversion.
    
    A Strategy receives ONLY a DecisionContext. It must never directly access
    external databases, HTTP clients, SEC scrapers, brokers, or system clocks.
    """
    name: str
    version: str

    def evaluate(self, context: DecisionContext) -> StrategyDecision:
        """Evaluate alpha logic against the immutable snapshot and portfolio state."""
        ...
