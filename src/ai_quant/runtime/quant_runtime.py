from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import uuid

from .clock import QuantClock
from .context import DecisionContext, RuntimeMode
from .snapshot import QuantSnapshot, SnapshotResolver
from .strategy import StrategyDecision, StrategyProtocol
from ..core.models import OrderIntent, PortfolioState, Side


@dataclass(frozen=True)
class RuntimeResult:
    """Complete quantitative execution output with cryptographic lineage."""
    context: DecisionContext
    decision: StrategyDecision
    order_intents: List[OrderIntent]


class UnifiedQuantRuntime:
    """Canonical Quant Decision Engine powering Backtest, Replay, Paper, and Live modes."""

    def __init__(
        self,
        resolver: SnapshotResolver,
        clock: QuantClock,
        mode: RuntimeMode = RuntimeMode.BACKTEST,
    ):
        self.resolver = resolver
        self.clock = clock
        self.mode = mode

    def evaluate(
        self,
        strategy: StrategyProtocol,
        symbol: str,
        portfolio: PortfolioState,
        run_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        parameters: Optional[dict] = None,
    ) -> RuntimeResult:
        decision_time = self.clock.now()
        
        # 1. Build immutable snapshot strictly known at decision_time
        snapshot = self.resolver.build_snapshot(
            symbols=[symbol],
            decision_time=decision_time,
        )

        # 2. Construct deterministic decision context
        context = DecisionContext.create(
            mode=self.mode,
            clock=self.clock,
            snapshot=snapshot,
            portfolio=portfolio,
            strategy_version=getattr(strategy, "version", "v1.0"),
            run_id=run_id,
            trace_id=trace_id,
            parameters=parameters,
        )

        # 3. Evaluate strategy
        decision = strategy.evaluate(context)

        # 4. Generate provenance-anchored OrderIntents
        order_intents: List[OrderIntent] = []
        if decision.side in (Side.BUY, Side.SELL) and decision.target_weight != 0:
            price = snapshot.get_feature(symbol, "close") or snapshot.get_feature(symbol, "price") or 100.0
            
            # Sizing calculation
            target_notional = abs(decision.target_weight) * portfolio.equity
            qty = decision.target_qty if decision.target_qty is not None else max(1, int(target_notional / price))
            notional = qty * price

            intent = OrderIntent(
                symbol=symbol,
                strategy_name=getattr(strategy, "name", "quant_strategy"),
                side=decision.side,
                qty=qty,
                reference_price=price,
                notional=notional,
                client_order_id=f"ord-{context.decision_id[:12]}",
                reason=f"[{strategy.name}] " + ("; ".join(decision.reasons) if decision.reasons else "Alpha target rebalance"),
                trace_id=context.trace_id,
                dataset_version=snapshot.snapshot_id[:16],
            )
            order_intents.append(intent)

        return RuntimeResult(
            context=context,
            decision=decision,
            order_intents=order_intents,
        )
