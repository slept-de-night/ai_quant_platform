import pytest
from datetime import datetime, timezone
import pandas as pd

from ai_quant.runtime.facts import ResearchFact
from ai_quant.runtime.snapshot import ResearchSnapshot
from ai_quant.runtime.changeset import ChangeSet, ChangeCategory
from ai_quant.runtime.context import ContextCompiler


def make_bars(prices, volumes=None):
    if volumes is None:
        volumes = [1000.0] * len(prices)
    return pd.DataFrame(
        {
            "open": [p - 0.5 for p in prices],
            "high": [p + 1.0 for p in prices],
            "low": [p - 1.0 for p in prices],
            "close": prices,
            "volume": volumes,
        }
    )


def make_snapshot(symbol: str, prices: list, volumes=None, facts=None, macro=None, run_id="run-01"):
    now = datetime.now(timezone.utc)
    bars = make_bars(prices, volumes)
    return ResearchSnapshot(
        snapshot_id=f"snap-{symbol}-{now.timestamp()}",
        run_id=run_id,
        symbol=symbol,
        as_of=now,
        content_hash=f"hash-{symbol}",
        market_bars={symbol: bars},
        facts=facts or [],
        macro_snapshot=macro,
    )


def test_changeset_initial_baseline():
    curr = make_snapshot("SPY", [500.0])
    cs = ChangeSet.detect(curr, None)
    assert cs.is_material is True
    assert cs.previous_snapshot_hash is None
    assert len(cs.items) == 1
    assert cs.items[0].category == ChangeCategory.STRUCTURAL


def test_changeset_immaterial_price_move():
    # 0.2% price move (500 -> 501)
    prev = make_snapshot("SPY", [500.0] * 20)
    curr = make_snapshot("SPY", [500.0] * 19 + [501.0])
    cs = ChangeSet.detect(curr, prev, price_threshold=0.015)
    assert cs.is_material is False
    assert cs.materiality_score < 0.30


def test_changeset_material_price_move():
    # 2.0% price move (500 -> 510)
    prev = make_snapshot("SPY", [500.0] * 20)
    curr = make_snapshot("SPY", [500.0] * 19 + [510.0])
    cs = ChangeSet.detect(curr, prev, price_threshold=0.015)
    assert cs.is_material is True
    assert any(it.category == ChangeCategory.PRICE_MOVE and it.is_material for it in cs.items)


def test_changeset_volume_shock():
    # 3.5x volume shock
    prev = make_snapshot("SPY", [500.0] * 20, [1000.0] * 20)
    curr = make_snapshot("SPY", [500.0] * 19 + [500.5], [1000.0] * 19 + [3500.0])
    cs = ChangeSet.detect(curr, prev, volume_shock_threshold=2.0)
    assert cs.is_material is True
    assert any(it.category == ChangeCategory.VOLUME_SHOCK and it.is_material for it in cs.items)


def test_changeset_new_sec_facts():
    now = datetime.now(timezone.utc)
    f1 = ResearchFact(
        fact_id="f-sec-01",
        symbol="AAPL",
        category="fundamental",
        key="revenue",
        value=90000000000.0,
        observed_at=now,
        known_at=now,
        as_of=now,
        source_type="sec_edgar",
    )
    prev = make_snapshot("AAPL", [200.0], facts=[])
    curr = make_snapshot("AAPL", [200.0], facts=[f1])
    cs = ChangeSet.detect(curr, prev)
    assert cs.is_material is True
    assert any(it.category == ChangeCategory.FILING_DISCLOSURE for it in cs.items)


def test_context_compiler():
    now = datetime.now(timezone.utc)
    fact = ResearchFact(
        fact_id="f-nvda-01",
        symbol="NVDA",
        category="fundamental",
        key="gross_margin",
        value=0.75,
        observed_at=now,
        known_at=now,
        as_of=now,
        source_type="sec_edgar",
    )
    snap = make_snapshot(
        "NVDA",
        [130.0],
        [50000.0],
        facts=[fact],
        macro={"cycle": "expansion", "fed_rate": 5.25},
    )
    compiled = ContextCompiler.compile(snap, task_type="thesis_generation", max_tokens=200)
    assert compiled.symbol == "NVDA"
    assert "NVDA" in compiled.rendered_prompt_text
    assert "gross_margin" in compiled.rendered_prompt_text
    assert "Macro Regime: expansion" in compiled.rendered_prompt_text
    assert compiled.estimated_tokens <= 200
