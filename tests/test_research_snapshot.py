from __future__ import annotations

from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List
import pandas as pd
import pytest

from ai_quant.runtime.facts import ResearchFact
from ai_quant.runtime.snapshot import (
    QuantSnapshot,
    ResearchSnapshot,
    ResearchSnapshotBuilder,
    SnapshotResolver,
)
from ai_quant.runtime.pit import PITStore
from ai_quant.runtime.handlers import ResearchRuntimeHandlers
from ai_quant.runtime.models import RuntimeTask


def _make_dummy_bars(base_price: float = 100.0, count: int = 300) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=count, freq="B", tz=timezone.utc)
    prices = [base_price + i * 0.2 for i in range(count)]
    return pd.DataFrame(
        {
            "open": [p - 0.1 for p in prices],
            "high": [p + 0.5 for p in prices],
            "low": [p - 0.5 for p in prices],
            "close": prices,
            "volume": [1000000.0] * count,
        },
        index=dates,
    )


class DummySECClient:
    def __init__(self, cik: int = 1045810):
        self.cik = cik

    def snapshot(self, symbol: str) -> Any:
        report = SimpleNamespace(
            fiscal_year=2025,
            end_date="2025-12-31",
            revenue=35000000000.0,
            revenue_growth_yoy=0.28,
            net_income=12000000000.0,
            net_margin=0.34,
            operating_cash_flow=15000000000.0,
            total_assets=80000000000.0,
            total_liabilities=30000000000.0,
        )
        return SimpleNamespace(
            symbol=symbol.upper(),
            cik=self.cik,
            annual_reports=[report],
        )


from ai_quant.intelligence.models import MacroSnapshot


class DummyFREDClient:
    def snapshot(self) -> Any:
        return MacroSnapshot(
            treasury_10y=4.25,
            fed_funds=5.25,
            cpi_yoy=2.8,
            unemployment=4.0,
            industrial_production_yoy=0.015,
            yield_curve_10y2y=0.20,
        )


def test_research_fact_creation_and_deterministic_hashing():
    t_obs = datetime(2026, 1, 15, 16, 0, tzinfo=timezone.utc)
    t_known = datetime(2026, 1, 15, 16, 30, tzinfo=timezone.utc)
    t_as_of = datetime(2026, 1, 15, 17, 0, tzinfo=timezone.utc)

    fact1 = ResearchFact(
        fact_id="fact-001",
        symbol="NVDA",
        category="technical",
        key="rsi_14",
        value=62.5,
        observed_at=t_obs,
        known_at=t_known,
        as_of=t_as_of,
        source_type="derived_technical",
        dataset_version="v1.0",
        confidence=0.85,
    )

    fact2 = ResearchFact(
        fact_id="fact-001",
        symbol="NVDA",
        category="technical",
        key="rsi_14",
        value=62.5,
        observed_at=t_obs,
        known_at=t_known,
        as_of=t_as_of,
        source_type="derived_technical",
        dataset_version="v1.0",
        confidence=0.85,
    )

    assert fact1.content_hash == fact2.content_hash
    assert len(fact1.content_hash) == 64


def test_research_snapshot_query_and_fact_partitioning():
    t_now = datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc)
    facts = [
        ResearchFact(
            fact_id="f1",
            symbol="NVDA",
            category="market",
            key="close",
            value=135.5,
            observed_at=t_now,
            known_at=t_now,
            as_of=t_now,
            source_type="market_data",
        ),
        ResearchFact(
            fact_id="f2",
            symbol="NVDA",
            category="technical",
            key="trend",
            value="long-term uptrend",
            observed_at=t_now,
            known_at=t_now,
            as_of=t_now,
            source_type="derived_technical",
        ),
        ResearchFact(
            fact_id="f3",
            symbol="NVDA",
            category="fundamental",
            key="net_margin",
            value=0.34,
            observed_at=t_now,
            known_at=t_now,
            as_of=t_now,
            source_type="sec_edgar",
        ),
    ]

    snapshot = ResearchSnapshot(
        snapshot_id="snap-test-01",
        run_id="run-001",
        symbol="NVDA",
        as_of=t_now,
        content_hash="abc123",
        facts=facts,
    )

    # Query specific fact by category and key
    f_close = snapshot.get_fact("market", "close")
    assert f_close is not None
    assert f_close.value == 135.5

    f_trend = snapshot.get_fact("technical", "trend")
    assert f_trend is not None
    assert f_trend.value == "long-term uptrend"

    # Category partitioning
    fund_facts = snapshot.get_facts_by_category("fundamental")
    assert len(fund_facts) == 1
    assert fund_facts[0].key == "net_margin"

    # Non-existent fact returns None
    assert snapshot.get_fact("macro", "gdp_growth") is None


def test_research_snapshot_builder_loads_once_and_generates_facts():
    load_counts: Dict[str, int] = {}

    def mock_data_loader(sym: str, limit: int = 1000) -> pd.DataFrame:
        load_counts[sym] = load_counts.get(sym, 0) + 1
        return _make_dummy_bars(base_price=150.0 if sym == "NVDA" else 100.0)

    sec_client = DummySECClient()
    fred_client = DummyFREDClient()

    builder = ResearchSnapshotBuilder(
        data_loader=mock_data_loader,
        sec_client=sec_client,
        fred_client=fred_client,
    )

    t_as_of = datetime(2026, 1, 15, 20, 0, tzinfo=timezone.utc)
    snapshot = builder.build(
        symbol="NVDA",
        run_id="run-builder-01",
        as_of=t_as_of,
        benchmarks=["SPY", "QQQ", "TLT", "GLD"],
    )

    # Verify all expected datasets loaded exactly once during snapshot build
    assert load_counts.get("NVDA") == 1
    assert load_counts.get("SPY") == 1
    assert load_counts.get("QQQ") == 1
    assert load_counts.get("TLT") == 1
    assert load_counts.get("GLD") == 1

    # Verify snapshot content and facts
    assert snapshot.symbol == "NVDA"
    assert snapshot.run_id == "run-builder-01"
    assert snapshot.snapshot_id.startswith("snap-")
    assert len(snapshot.facts) > 0

    # Verify market facts exist
    close_fact = snapshot.get_fact("market", "close", "NVDA")
    assert close_fact is not None
    assert close_fact.value > 0

    # Verify technical facts exist
    tech_score = snapshot.get_fact("technical", "directional_score", "NVDA")
    assert tech_score is not None

    # Verify fundamental facts exist
    fund_growth = snapshot.get_fact("fundamental", "revenue_growth_yoy", "NVDA")
    assert fund_growth is not None
    assert fund_growth.value == 0.28

    # Verify macro facts exist
    macro_fed = snapshot.get_fact("macro", "fed_funds_rate")
    assert macro_fed is not None
    assert macro_fed.value == 5.25

    macro_cpi = snapshot.get_fact("macro", "cpi_yoy")
    assert macro_cpi is not None
    assert macro_cpi.value == 2.8

    macro_yc = snapshot.get_fact("macro", "yield_curve_10y2y")
    assert macro_yc is not None
    assert macro_yc.value == 0.20


def test_handlers_reuse_snapshot_without_reloading_data(tmp_path):
    load_counts: Dict[str, int] = {}

    def mock_data_loader(sym: str, limit: int = 1000) -> pd.DataFrame:
        load_counts[sym] = load_counts.get(sym, 0) + 1
        return _make_dummy_bars(base_price=100.0)

    sec_client = DummySECClient()
    fred_client = DummyFREDClient()

    builder = ResearchSnapshotBuilder(
        data_loader=mock_data_loader,
        sec_client=sec_client,
        fred_client=fred_client,
    )
    snapshot = builder.build(
        symbol="NVDA",
        run_id="run-handlers-reuse",
    )

    # Record load counts after snapshot build
    initial_loads = dict(load_counts)

    # Initialize handlers with pre-built snapshot and valid SQLite db
    from ai_quant.core.config import Settings
    cfg = Settings(
        db_path=str(tmp_path / "test_handlers.db"),
        sec_user_agent="TestAgent test@example.com",
        fred_api_key="mock_fred_key",
        openai_api_key=None,
    )
    handlers = ResearchRuntimeHandlers(
        cfg=cfg,
        data_loader=mock_data_loader,
        execute_ai=False,
        snapshot=snapshot,
    )

    # Execute multiple deterministic tasks across the research DAG
    extract_out = handlers.extract(
        RuntimeTask(
            task_id="t1",
            root_id="root-1",
            agent_role="technical_agent",
            task_type="extract",
            objective="Analyze technicals",
            symbol="NVDA",
            available_at=datetime.now(timezone.utc),
            idempotency_key="t1",
        ),
        deps={},
    )
    assert extract_out["kind"] == "technical"
    assert "view" in extract_out

    fund_out = handlers.fundamental(
        RuntimeTask(
            task_id="t2",
            root_id="root-1",
            agent_role="fundamental_agent",
            task_type="fundamental_review",
            objective="Analyze fundamentals",
            symbol="NVDA",
            available_at=datetime.now(timezone.utc),
            idempotency_key="t2",
        ),
        deps={},
    )
    assert fund_out["kind"] == "fundamental"

    micro_out = handlers.trend(
        RuntimeTask(
            task_id="t3",
            root_id="root-1",
            agent_role="microtrend_agent",
            task_type="trend_review",
            objective="Analyze microtrends",
            symbol="NVDA",
            available_at=datetime.now(timezone.utc),
            idempotency_key="t3",
        ),
        deps={},
    )
    assert micro_out["kind"] == "microtrend"

    mega_out = handlers.trend(
        RuntimeTask(
            task_id="t4",
            root_id="root-1",
            agent_role="megatrend_agent",
            task_type="trend_review",
            objective="Analyze megatrends",
            symbol="NVDA",
            available_at=datetime.now(timezone.utc),
            idempotency_key="t4",
        ),
        deps={},
    )
    assert mega_out["kind"] == "megatrend"

    # Invariant: NO additional data_loader calls were made because handlers reused the snapshot!
    assert load_counts == initial_loads


def test_research_snapshot_to_pit_store_integration():
    t_now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    facts = [
        ResearchFact(
            fact_id="obs-close",
            symbol="NVDA",
            category="market",
            key="close",
            value=140.0,
            observed_at=t_now,
            known_at=t_now,
            as_of=t_now,
            source_type="market_data",
        ),
        ResearchFact(
            fact_id="obs-score",
            symbol="NVDA",
            category="technical",
            key="directional_score",
            value=0.75,
            observed_at=t_now,
            known_at=t_now,
            as_of=t_now,
            source_type="derived_technical",
        ),
    ]

    snapshot = ResearchSnapshot(
        snapshot_id="snap-pit-01",
        run_id="run-pit-01",
        symbol="NVDA",
        as_of=t_now,
        content_hash="hash123",
        facts=facts,
    )

    pit_obs = snapshot.to_pit_observations()
    assert len(pit_obs) == 2

    store = PITStore()
    store.record_many(pit_obs)

    # Query PITStore
    obs_res = store.get_known_at("NVDA", as_of_time=t_now)
    assert len(obs_res) == 2
    assert store.get_latest_feature("NVDA", "market:close", t_now).value == 140.0
    assert store.get_latest_feature("NVDA", "technical:directional_score", t_now).value == 0.75
