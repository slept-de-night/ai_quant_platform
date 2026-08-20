from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pytest

from ai_quant.core.models import PortfolioState, Side
from ai_quant.runtime.pit import PITObservation, PITStore
from ai_quant.runtime.clock import HistoricalClock, LiveClock
from ai_quant.runtime.snapshot import QuantSnapshot, SnapshotResolver
from ai_quant.runtime.context import DecisionContext, RuntimeMode
from ai_quant.runtime.strategy import StrategyDecision, StrategyProtocol
from ai_quant.runtime.quant_runtime import UnifiedQuantRuntime


class DummyMomentumStrategy:
    """Deterministic test strategy implementing StrategyProtocol."""
    name: str = "test_momentum"
    version: str = "v1.0"

    def evaluate(self, context: DecisionContext) -> StrategyDecision:
        # Strategy receives ONLY DecisionContext (no direct DB or API access)
        close_price = context.snapshot.get_feature("NVDA", "close") or 100.0
        ma_50 = context.snapshot.get_feature("NVDA", "ma_50") or 90.0

        if close_price > ma_50:
            return StrategyDecision(
                symbol="NVDA",
                side=Side.BUY,
                target_weight=0.08,
                confidence=0.85,
                reasons=[f"Price ${close_price} > 50-day MA ${ma_50}"],
            )
        return StrategyDecision(
            symbol="NVDA",
            side=Side.HOLD,
            target_weight=0.0,
            confidence=0.50,
            reasons=["No trend trigger"],
        )


def test_no_future_data_anti_lookahead():
    """B1-01 / B1-07: Data known at T+5 must be completely invisible at T+3."""
    store = PITStore()
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    t_effective = datetime(2025, 12, 31, 0, 0, tzinfo=timezone.utc)  # Quarter end
    t_known_early = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
    t_known_future = datetime(2026, 2, 15, 0, 0, tzinfo=timezone.utc) # 10-K filing date

    # Record historical observation (known early)
    store.record(
        PITObservation(
            observation_id="obs-1",
            symbol="NVDA",
            feature_name="close",
            value=120.0,
            effective_at=t_effective,
            known_at=t_known_early,
        )
    )

    # Record future observation (filed in Feb)
    store.record(
        PITObservation(
            observation_id="obs-2",
            symbol="NVDA",
            feature_name="revenue",
            value=35000000000.0,
            effective_at=t_effective,
            known_at=t_known_future,
        )
    )

    # Query as of Jan 15 (before filing)
    as_of_jan15 = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
    obs_jan = store.get_known_at("NVDA", as_of_time=as_of_jan15)
    
    assert len(obs_jan) == 1
    assert obs_jan[0].feature_name == "close"
    assert store.get_latest_feature("NVDA", "revenue", as_of_jan15) is None

    # Query as of Feb 20 (after filing)
    as_of_feb20 = datetime(2026, 2, 20, 0, 0, tzinfo=timezone.utc)
    obs_feb = store.get_known_at("NVDA", as_of_time=as_of_feb20)
    assert len(obs_feb) == 2
    assert store.get_latest_feature("NVDA", "revenue", as_of_feb20).value == 35000000000.0


def test_restatement_visibility():
    """B1-04: Prior simulation accesses original value; post-restatement simulation accesses restated value."""
    store = PITStore()
    t_effective = datetime(2025, 9, 30, 0, 0, tzinfo=timezone.utc)
    t_original_pub = datetime(2025, 11, 1, 0, 0, tzinfo=timezone.utc)
    t_restatement_pub = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)

    # Original reported EPS = 2.10
    store.record(
        PITObservation(
            observation_id="eps-orig",
            symbol="NVDA",
            feature_name="eps",
            value=2.10,
            effective_at=t_effective,
            known_at=t_original_pub,
        )
    )

    # Restated reported EPS = 1.84
    store.record(
        PITObservation(
            observation_id="eps-restate",
            symbol="NVDA",
            feature_name="eps",
            value=1.84,
            effective_at=t_effective,
            known_at=t_restatement_pub,
            is_restatement=True,
        )
    )

    # Simulation running in December 2025 sees original 2.10
    as_of_dec = datetime(2025, 12, 15, 0, 0, tzinfo=timezone.utc)
    obs_dec = store.get_latest_feature("NVDA", "eps", as_of_dec)
    assert obs_dec is not None
    assert obs_dec.value == 2.10

    # Simulation running in April 2026 sees restated 1.84
    as_of_apr = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
    obs_apr = store.get_latest_feature("NVDA", "eps", as_of_apr)
    assert obs_apr is not None
    assert obs_apr.value == 1.84


def test_quant_snapshot_deterministic_hashing():
    """B1-05 / B1-09: Identical observations produce identical cryptographic snapshot_id."""
    t_dec = datetime(2026, 1, 15, 16, 0, tzinfo=timezone.utc)
    obs1 = PITObservation("1", "NVDA", "close", 130.0, t_dec, t_dec)
    obs2 = PITObservation("2", "NVDA", "ma_50", 120.0, t_dec, t_dec)

    snap_a = QuantSnapshot.create(t_dec, [obs1, obs2])
    snap_b = QuantSnapshot.create(t_dec, [obs2, obs1])  # Reverse order

    assert snap_a.snapshot_id == snap_b.snapshot_id
    assert len(snap_a.snapshot_id) == 64  # SHA256 hex length


def test_unified_quant_runtime_and_lineage():
    """B1-06 / B1-08 / B1-10: Evaluates strategy and produces OrderIntent with full provenance."""
    store = PITStore()
    t_sim = datetime(2026, 1, 15, 16, 0, tzinfo=timezone.utc)
    store.record(PITObservation("c-1", "NVDA", "close", 135.0, t_sim, t_sim))
    store.record(PITObservation("m-1", "NVDA", "ma_50", 125.0, t_sim, t_sim))

    resolver = SnapshotResolver(store)
    clock = HistoricalClock(t_sim)
    runtime = UnifiedQuantRuntime(resolver, clock, mode=RuntimeMode.BACKTEST)

    portfolio = PortfolioState(
        equity=100000.0,
        cash=100000.0,
        gross_exposure=0.0,
        daily_pnl=0.0,
        peak_equity=100000.0,
    )

    strategy = DummyMomentumStrategy()
    result = runtime.evaluate(
        strategy=strategy,
        symbol="NVDA",
        portfolio=portfolio,
        run_id="run-test-01",
        trace_id="trace-test-01",
    )

    assert result.decision.side == Side.BUY
    assert len(result.order_intents) == 1
    
    order = result.order_intents[0]
    assert order.symbol == "NVDA"
    assert order.side == Side.BUY
    assert order.trace_id == "trace-test-01"
    assert order.dataset_version == result.context.snapshot.snapshot_id[:16]
    assert order.notional > 0
    assert order.qty > 0
