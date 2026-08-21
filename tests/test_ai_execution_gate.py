import os
import pytest
import sqlite3
from unittest.mock import MagicMock

from ai_quant.core.config import Settings
from ai_quant.runtime.gate import (
    AIExecutionGate,
    ExecutionDecision,
    ExecutionKind,
    GateRequest,
    DETERMINISTIC_TASK_TYPES,
)
from ai_quant.runtime.models import DelegationRequest
from ai_quant.runtime.orchestrator import TaskOrchestrator, TaskRuntime, WorkerPool
from ai_quant.runtime.handlers import ResearchRuntimeHandlers
from ai_quant.data.market_data import synthetic_bars


@pytest.fixture
def test_cfg(tmp_path):
    db_file = tmp_path / "test_quant.db"
    return Settings(
        db_path=str(db_file),
        agent_memory_dir=str(tmp_path / "memory"),
        openai_api_key="mock-key-for-test",
    )


def test_deterministic_tasks_never_invoke_ai(test_cfg):
    gate = AIExecutionGate(test_cfg)
    
    for task_type in DETERMINISTIC_TASK_TYPES:
        req = GateRequest(
            task_type=task_type,
            symbol="AAPL",
            complexity=0.9,
            criticality=0.9,
            financial_impact=0.9,
            has_new_filing=True,
            has_material_change=True,
        )
        decision = gate.evaluate(req)
        assert decision.kind == ExecutionKind.DETERMINISTIC
        assert decision.materiality == 0.0
        assert decision.model_route is None
        assert "deterministic" in decision.reason.lower()


def test_exact_cache_hit_requires_verified_result(test_cfg):
    gate = AIExecutionGate(test_cfg)

    # A bare cache_key is NOT proof of a cached result -> must NOT be CACHE.
    req = GateRequest(
        task_type="web_research",
        symbol="NVDA",
        cache_key="sha256:abc123456789",
        force_refresh=False,
    )
    decision = gate.evaluate(req)
    assert decision.kind != ExecutionKind.CACHE
    assert decision.kind == ExecutionKind.SKIP
    assert decision.model_route is None

    # After a stored result is registered, the same cache_key is a verified hit.
    gate.register_cached_result(
        cache_key="sha256:abc123456789",
        task_type="web_research",
        symbol="NVDA",
        context_hash=req.context_hash,
    )
    decision2 = gate.evaluate(req)
    assert decision2.kind == ExecutionKind.CACHE
    assert decision2.cache_key == "sha256:abc123456789"
    assert decision2.model_route is None

    # force_refresh=True must bypass even a verified cache.
    req_force = GateRequest(
        task_type="web_research",
        symbol="NVDA",
        cache_key="sha256:abc123456789",
        force_refresh=True,
    )
    decision_force = gate.evaluate(req_force)
    assert decision_force.kind == ExecutionKind.AI


def test_materiality_and_change_gating_web_research(test_cfg):
    gate = AIExecutionGate(test_cfg)

    # 1. Routine refresh: tiny price move (0.2%), no new filing, no material change -> SKIP
    req_routine = GateRequest(
        task_type="web_research",
        symbol="AAPL",
        price_move=0.002,
        has_new_filing=False,
        has_material_change=False,
        force_refresh=False,
    )
    decision_routine = gate.evaluate(req_routine)
    assert decision_routine.kind == ExecutionKind.SKIP
    assert "routine data refresh" in decision_routine.reason.lower() or "price move" in decision_routine.reason.lower()
    assert decision_routine.model_route is None

    # 2. Material price move (5.0%) -> AI
    req_move = GateRequest(
        task_type="web_research",
        symbol="AAPL",
        price_move=0.05,
        has_new_filing=False,
        has_material_change=False,
    )
    decision_move = gate.evaluate(req_move)
    assert decision_move.kind == ExecutionKind.AI
    assert decision_move.preferred_tier == "balanced"
    assert decision_move.model_route is not None

    # 3. New filing -> AI
    req_filing = GateRequest(
        task_type="web_research",
        symbol="AAPL",
        has_new_filing=True,
    )
    decision_filing = gate.evaluate(req_filing)
    assert decision_filing.kind == ExecutionKind.AI


def test_contradiction_claims_gating(test_cfg):
    gate = AIExecutionGate(test_cfg)

    # Less than 2 claims -> SKIP
    req_one = GateRequest(
        task_type="contradiction",
        symbol="MSFT",
        claims_count=1,
    )
    decision_one = gate.evaluate(req_one)
    assert decision_one.kind == ExecutionKind.SKIP
    assert "insufficient claims" in decision_one.reason.lower()

    # >= 2 claims with potential contradiction -> AI
    req_multi = GateRequest(
        task_type="contradiction",
        symbol="MSFT",
        claims_count=4,
        has_contradiction=True,
    )
    decision_multi = gate.evaluate(req_multi)
    assert decision_multi.kind == ExecutionKind.AI
    assert decision_multi.preferred_tier == "balanced"
    assert decision_multi.model_route is not None


def test_scenario_falsification_materiality_gating(test_cfg):
    gate = AIExecutionGate(test_cfg)

    # 1. No change -> SKIP
    req_no_change = GateRequest(
        task_type="scenario_synthesis",
        symbol="GOOGL",
        has_material_change=False,
        has_new_filing=False,
        has_contradiction=False,
        force_refresh=False,
    )
    decision_no_change = gate.evaluate(req_no_change)
    assert decision_no_change.kind == ExecutionKind.SKIP

    # 2. Material change -> AI (frontier)
    req_material = GateRequest(
        task_type="scenario_synthesis",
        symbol="GOOGL",
        has_material_change=True,
        financial_impact=0.7,
    )
    decision_material = gate.evaluate(req_material)
    assert decision_material.kind == ExecutionKind.AI
    assert decision_material.preferred_tier == "frontier"


def test_gate_audit_logging_and_summary_stats(test_cfg):
    gate = AIExecutionGate(test_cfg)
    run_id = "run-test-001"

    # Register a verified cached result so the cache_key below is a real hit.
    gate.register_cached_result(cache_key="k1", task_type="web_research", symbol="SPY")

    # Evaluate multiple different requests
    gate.evaluate(GateRequest(task_type="extract", symbol="SPY", run_id=run_id))
    gate.evaluate(GateRequest(task_type="fundamental_review", symbol="SPY", run_id=run_id))
    gate.evaluate(GateRequest(task_type="trend_review", symbol="SPY", run_id=run_id))
    gate.evaluate(GateRequest(task_type="web_research", symbol="SPY", price_move=0.001, run_id=run_id))
    gate.evaluate(GateRequest(task_type="web_research", symbol="SPY", cache_key="k1", run_id=run_id))
    gate.evaluate(GateRequest(task_type="alpha_generation", symbol="SPY", run_id=run_id))

    stats = gate.summary_stats(run_id=run_id)
    assert stats["total_decisions"] == 6
    assert stats["deterministic_tasks"] == 3
    assert stats["skipped_tasks"] == 1
    assert stats["cached_tasks"] == 1
    assert stats["ai_tasks"] == 1
    assert stats["ai_calls_avoided"] == 5
    assert stats["ai_avoidance_ratio"] == 5.0 / 6.0

    recent = gate.recent_decisions(limit=10)
    assert len(recent) == 6
    assert all("task_type" in r for r in recent)
    assert all("reason" in r for r in recent)


def test_task_orchestrator_integration_with_gate(test_cfg):
    orchestrator = TaskOrchestrator(test_cfg)
    nodes = orchestrator.plan_research("NVDA")
    
    # 13 nodes planned
    assert len(nodes) == 13
    
    # Find deterministic nodes
    tech_nodes = [n for n in nodes if n.task_type == "extract"]
    assert len(tech_nodes) == 1
    assert tech_nodes[0].route is None
    assert tech_nodes[0].execution_decision is not None
    assert tech_nodes[0].execution_decision.kind == ExecutionKind.DETERMINISTIC

    fund_nodes = [n for n in nodes if n.task_type == "fundamental_review"]
    assert len(fund_nodes) == 1
    assert fund_nodes[0].route is None
    assert fund_nodes[0].execution_decision.kind == ExecutionKind.DETERMINISTIC

    audit_nodes = [n for n in nodes if n.task_type == "critical_review"]
    assert len(audit_nodes) == 1
    assert audit_nodes[0].route is None
    assert audit_nodes[0].execution_decision.kind == ExecutionKind.DETERMINISTIC


def test_routine_refresh_acceptance_zero_ai_calls(test_cfg):
    """Acceptance test: Prove routine no-change research refresh completes with 0 AI calls."""
    data_loader = lambda sym, bars: synthetic_bars(sym, bars)
    runtime = TaskRuntime(test_cfg)
    handlers = ResearchRuntimeHandlers(test_cfg, data_loader, execute_ai=False)
    pool = WorkerPool(runtime, handlers.handlers())

    orchestrator = TaskOrchestrator(test_cfg)
    nodes = orchestrator.plan_research("AAPL")
    root_id = nodes[0].root_id

    # Enqueue tasks in runtime
    runtime.enqueue_plan(nodes)

    # Run all tasks through worker pool
    results = pool.run_until_idle()
    assert len(results) == 13

    # Check execution gate stats for this run
    gate_stats = orchestrator.gate.summary_stats(run_id=root_id)
    assert gate_stats["ai_tasks"] == 0, f"Expected 0 AI calls on routine refresh, got {gate_stats['ai_tasks']}"
    assert gate_stats["ai_calls_avoided"] == gate_stats["total_decisions"]


def test_handler_gate_respects_task_payload_force_refresh(test_cfg):
    """When execute_ai=True, gate can still skip if force_refresh is not requested in payload."""
    data_loader = lambda sym, bars: synthetic_bars(sym, bars)
    handlers = ResearchRuntimeHandlers(test_cfg, data_loader, execute_ai=True)

    from datetime import datetime, timezone
    from ai_quant.runtime.models import RuntimeTask

    # Task without force_refresh (default) and low materiality -> skips AI
    task_routine = RuntimeTask(
        task_id="t-web-1",
        root_id="root-1",
        agent_role="web_research_agent",
        task_type="web_research",
        objective="routine research",
        symbol="SPY",
        payload={"force_refresh": False},
        available_at=datetime.now(timezone.utc),
        idempotency_key="k1",
    )
    res1 = handlers.web_research(task_routine, deps={})
    # Since materiality is low and force_refresh is False, decision should be SKIP
    assert res1.get("skipped") is True
    assert res1["execution_decision"]["kind"] == "skip"

    # Task with explicit force_refresh=True
    task_forced = RuntimeTask(
        task_id="t-web-2",
        root_id="root-2",
        agent_role="web_research_agent",
        task_type="web_research",
        objective="forced research",
        symbol="SPY",
        payload={"force_refresh": True},
        available_at=datetime.now(timezone.utc),
        idempotency_key="k2",
    )
    # With force_refresh=True, evaluate returns AI kind
    decision = handlers.gate.evaluate(
        GateRequest(
            task_type="web_research",
            symbol="SPY",
            force_refresh=True,
        )
    )
    assert decision.kind == ExecutionKind.AI
