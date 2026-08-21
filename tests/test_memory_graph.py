from datetime import datetime, timedelta, timezone
from ai_quant.agent_memory import (
    AgentMemoryStore,
    ClaimDirection,
    MemoryKind,
    MemoryNote,
    calculate_decayed_confidence,
    classify_claim_direction,
    detect_contradictions,
    extract_entities,
)


def test_entity_extraction():
    content = "Bullish on $NVDA and TSLA due to semiconductor demand growth and falling inflation expectations from the Fed."
    entities = extract_entities(content, default_symbol="NVDA")
    assert "NVDA" in entities["symbols"]
    assert "TSLA" in entities["symbols"]
    assert "technology" in entities["sectors"]
    assert "inflation" in entities["macro_factors"]
    assert "fed" in entities["macro_factors"]


def test_claim_direction_classification():
    assert classify_claim_direction("Bullish breakout and strong revenue acceleration") == ClaimDirection.BULLISH
    assert classify_claim_direction("Bearish outlook with decelerating growth and contraction") == ClaimDirection.BEARISH
    assert classify_claim_direction("Severe warning: potential fraud and accounting manipulation risk") == ClaimDirection.RISK_ALERT


def test_confidence_decay():
    now = datetime.now(timezone.utc)
    t0 = now - timedelta(days=30)
    # At 30 days (1 half-life), confidence 0.8 should decay to ~0.40
    decayed = calculate_decayed_confidence(initial_confidence=0.8, created_at=t0, as_of=now, half_life_days=30.0)
    assert 0.39 <= decayed <= 0.41

    t60 = now - timedelta(days=60)
    # At 60 days (2 half-lives), confidence 0.8 should decay to ~0.20
    decayed_60 = calculate_decayed_confidence(initial_confidence=0.8, created_at=t60, as_of=now, half_life_days=30.0)
    assert 0.19 <= decayed_60 <= 0.21


def test_contradiction_detection():
    now = datetime.now(timezone.utc)
    existing_note = MemoryNote(
        id=1,
        agent="fundamental_analyst",
        kind=MemoryKind.HYPOTHESIS,
        symbol="AAPL",
        content="Bullish growth thesis with accelerating iPhone demand and margin expansion",
        confidence=0.85,
        created_at=now,
    )

    # New bearish claim contradicts the existing bullish note
    contradictions = detect_contradictions(
        new_content="Bearish reversal: supply chain data indicates iPhone shipment contraction",
        new_symbol="AAPL",
        new_confidence=0.80,
        existing_notes=[existing_note],
    )
    assert len(contradictions) == 1
    assert contradictions[0].conflicting_note_id == 1
    assert "Directional conflict on AAPL" in contradictions[0].reason


def test_memory_store_hygiene_and_deduplication(tmp_path):
    db_path = str(tmp_path / "memory_hygiene.sqlite3")
    md_dir = str(tmp_path / "journals")
    store = AgentMemoryStore(db_path, md_dir)

    note1 = MemoryNote(
        agent="quant_researcher",
        kind=MemoryKind.OBSERVATION,
        symbol="MSFT",
        content="Cloud revenue growth remained resilient at 28 percent YoY",
        confidence=0.75,
        decision_id="decision-101",
    )
    res1 = store.add_with_hygiene(note1)
    assert res1["action"] == "added"
    assert res1["note"].id is not None

    # Adding exact duplicate content should be detected and skipped
    note2 = MemoryNote(
        agent="quant_researcher",
        kind=MemoryKind.OBSERVATION,
        symbol="MSFT",
        content="Cloud revenue growth remained resilient at 28 percent YoY",
        confidence=0.75,
        decision_id="decision-102",
    )
    res2 = store.add_with_hygiene(note2, dedup_threshold=0.85)
    assert res2["action"] == "duplicate_skipped"
    assert res2["duplicate_of_id"] == res1["note"].id


def test_decision_audit_trail_and_decayed_summary(tmp_path):
    db_path = str(tmp_path / "memory_audit.sqlite3")
    md_dir = str(tmp_path / "journals")
    store = AgentMemoryStore(db_path, md_dir)

    d_id = "exec-trade-nvda-20260821"
    store.add(
        MemoryNote(
            agent="risk_agent",
            kind=MemoryKind.DECISION,
            symbol="NVDA",
            content="Allocating 4 percent weight after positive earnings surprise",
            confidence=0.90,
            decision_id=d_id,
        )
    )
    store.add(
        MemoryNote(
            agent="execution_agent",
            kind=MemoryKind.LESSON,
            symbol="NVDA",
            content="Filled via TWAP over 30 minutes with minimal slippage",
            confidence=0.95,
            decision_id=d_id,
        )
    )

    trail = store.get_audit_trail(d_id)
    assert len(trail) == 2
    assert trail[0].decision_id == d_id
    assert trail[1].decision_id == d_id

    # Test decayed summary
    decayed_items = store.get_decayed_summary("risk_agent", symbol="NVDA")
    assert len(decayed_items) == 1
    assert "decayed_confidence" in decayed_items[0]
    assert "entities" in decayed_items[0]
