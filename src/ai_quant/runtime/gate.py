from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from ..core.config import Settings
from .router import ModelDecision, ModelRouter, RouteRequest


class ExecutionKind(str, Enum):
    SKIP = "skip"
    DETERMINISTIC = "deterministic"
    CACHE = "cache"
    AI = "ai"


class GateRequest(BaseModel):
    task_type: str
    symbol: Optional[str] = None
    agent_role: Optional[str] = None
    objective: Optional[str] = None
    force_refresh: bool = False
    cache_key: Optional[str] = None
    context_hash: Optional[str] = None
    price_move: Optional[float] = None
    has_new_filing: bool = False
    has_material_change: bool = False
    has_contradiction: bool = False
    claims_count: int = 0
    complexity: float = Field(default=0.5, ge=0, le=1)
    criticality: float = Field(default=0.5, ge=0, le=1)
    ambiguity: float = Field(default=0.3, ge=0, le=1)
    financial_impact: float = Field(default=0.0, ge=0, le=1)
    needs_tools: bool = False
    needs_web: bool = False
    quality_first: bool = False
    remaining_budget_ratio: float = Field(default=1.0, ge=0, le=1)
    allow_empirical_override: bool = True
    allow_degrade: bool = True
    run_id: Optional[str] = None
    materiality_threshold: float = 0.30


class ExecutionDecision(BaseModel):
    kind: ExecutionKind
    reason: str
    materiality: float = Field(default=0.0, ge=0, le=1)
    freshness_required: bool = False
    cache_key: Optional[str] = None
    ai_task_type: Optional[str] = None
    preferred_tier: Optional[str] = None
    model_route: Optional[ModelDecision] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


GATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS execution_gate_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    task_type TEXT NOT NULL,
    symbol TEXT,
    kind TEXT NOT NULL,
    materiality REAL NOT NULL,
    freshness_required INTEGER NOT NULL,
    cache_key TEXT,
    preferred_tier TEXT,
    reason TEXT NOT NULL,
    run_id TEXT,
    details_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gate_run_id ON execution_gate_decisions(run_id);
CREATE INDEX IF NOT EXISTS idx_gate_kind ON execution_gate_decisions(kind);
CREATE TABLE IF NOT EXISTS cached_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT NOT NULL UNIQUE,
    task_type TEXT,
    symbol TEXT,
    context_hash TEXT,
    result_ref TEXT,
    stored_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cached_cache_key ON cached_results(cache_key);
"""

DETERMINISTIC_TASK_TYPES = {
    "extract",
    "technical",
    "fundamental_review",
    "sec_xbrl",
    "trend_review",
    "microtrend",
    "megatrend",
    "critical_review",
    "audit",
    "research_digest",
    "research_program",
    "classify",
    "format",
    "journal",
    "deduplicate",
    "source_tier",
    "task_decomposition",
}


class AIExecutionGate:
    """Deterministic AI Execution Gate.
    
    Evaluates whether tasks require AI reasoning, can be computed deterministically,
    can reuse cached results, or should be skipped due to lack of material change.
    """

    def __init__(self, cfg: Settings, router: Optional[ModelRouter] = None):
        self.cfg = cfg
        self.router = router or ModelRouter(cfg)
        with sqlite3.connect(cfg.db_path) as con:
            con.executescript(GATE_SCHEMA)

    @staticmethod
    def _heuristic_materiality(req: GateRequest) -> float:
        base = 0.40 * req.complexity + 0.30 * req.criticality + 0.15 * req.ambiguity + 0.15 * req.financial_impact
        if req.has_new_filing:
            base = min(1.0, base + 0.35)
        if req.has_material_change:
            base = min(1.0, base + 0.25)
        if req.has_contradiction:
            base = min(1.0, base + 0.20)
        if req.price_move is not None:
            move_impact = min(0.30, abs(req.price_move) * 5.0)
            base = min(1.0, base + move_impact)
        return round(base, 4)

    def evaluate(self, req: GateRequest) -> ExecutionDecision:
        task = req.task_type.lower().strip()
        materiality = self._heuristic_materiality(req)

        # 0. Manager / Coordinator Roles are Deterministic Aggregators
        if req.agent_role in {"research_manager", "market_structure_manager", "evidence_manager", "thesis_manager"}:
            decision = ExecutionDecision(
                kind=ExecutionKind.DETERMINISTIC,
                reason="Manager coordination and child result aggregation is purely deterministic.",
                materiality=0.0,
                freshness_required=False,
            )
            self.record(req, decision)
            return decision

        # 1. Purely Deterministic Tasks
        if task in DETERMINISTIC_TASK_TYPES:
            decision = ExecutionDecision(
                kind=ExecutionKind.DETERMINISTIC,
                reason="Task is purely deterministic numerical, structural, or parsing logic; no AI reasoning required.",
                materiality=0.0,
                freshness_required=False,
            )
            self.record(req, decision)
            return decision

        # 2. Exact Cache Hit Requires Verified Stored Evidence
        # A supplied cache_key is NOT proof that a valid cached result exists.
        # Only emit CACHE when the registry holds an actual stored result.
        if req.cache_key and not req.force_refresh and self.has_verified_cache(req.cache_key, req.symbol, req.context_hash):
            decision = ExecutionDecision(
                kind=ExecutionKind.CACHE,
                reason=f"Verified cached reasoning output available for cache_key={req.cache_key}.",
                materiality=materiality,
                cache_key=req.cache_key,
                freshness_required=False,
            )
            self.record(req, decision)
            return decision

        # 3. Contradiction Checking
        if task == "contradiction":
            if req.claims_count < 2:
                decision = ExecutionDecision(
                    kind=ExecutionKind.SKIP,
                    reason="Insufficient claims for contradiction analysis (<2 claims); skipping AI pass.",
                    materiality=0.0,
                )
                self.record(req, decision)
                return decision

            if not req.force_refresh and not req.has_contradiction and not req.has_material_change and req.claims_count < 3:
                decision = ExecutionDecision(
                    kind=ExecutionKind.SKIP,
                    reason="No new or disputed claims present; skipping contradiction check.",
                    materiality=materiality,
                )
                self.record(req, decision)
                return decision

            route = self._resolve_route(req, "balanced")
            decision = ExecutionDecision(
                kind=ExecutionKind.AI,
                reason=f"Analyzing {req.claims_count} sanitized claims for direct material semantic contradictions.",
                materiality=materiality,
                ai_task_type="contradiction",
                preferred_tier="balanced",
                model_route=route,
            )
            self.record(req, decision)
            return decision

        # 4. Web Evidence Research
        if task == "web_research":
            if not req.symbol:
                decision = ExecutionDecision(
                    kind=ExecutionKind.SKIP,
                    reason="No target symbol specified for web evidence collection.",
                    materiality=0.0,
                )
                self.record(req, decision)
                return decision

            price_move = abs(req.price_move) if req.price_move is not None else 0.0
            if not req.force_refresh and not req.has_material_change and not req.has_new_filing and price_move < 0.015:
                decision = ExecutionDecision(
                    kind=ExecutionKind.SKIP,
                    reason="Routine data refresh: price move (<1.5%) and fundamental state unchanged; no new web research needed.",
                    materiality=materiality,
                )
                self.record(req, decision)
                return decision

            route = self._resolve_route(req, "balanced", needs_web=True, needs_tools=True)
            decision = ExecutionDecision(
                kind=ExecutionKind.AI,
                reason="Collecting and verifying primary/trusted web evidence for material developments.",
                materiality=materiality,
                ai_task_type="web_research",
                preferred_tier="balanced",
                model_route=route,
            )
            self.record(req, decision)
            return decision

        # 5. Future Scenario Synthesis & Falsification
        if task in {"scenario_synthesis", "falsification"}:
            if not req.force_refresh and not req.has_material_change and not req.has_new_filing and not req.has_contradiction:
                decision = ExecutionDecision(
                    kind=ExecutionKind.SKIP,
                    reason="Market structure, verified evidence, and macro regime are unchanged; existing scenario thesis persists.",
                    materiality=materiality,
                )
                self.record(req, decision)
                return decision

            tier = "frontier" if materiality >= 0.55 else "balanced"
            route = self._resolve_route(req, tier)
            decision = ExecutionDecision(
                kind=ExecutionKind.AI,
                reason=f"Synthesizing conditional scenarios / falsification tests following material evidence or regime changes (materiality={materiality:.2f}).",
                materiality=materiality,
                ai_task_type=task,
                preferred_tier=tier,
                model_route=route,
            )
            self.record(req, decision)
            return decision

        # 6. Alpha Hypothesis Generation
        if task in {"alpha_generation", "hypothesis"}:
            route = self._resolve_route(req, "frontier")
            decision = ExecutionDecision(
                kind=ExecutionKind.AI,
                reason="Exploratory multi-factor alpha hypothesis formulation.",
                materiality=materiality,
                ai_task_type=task,
                preferred_tier="frontier",
                model_route=route,
            )
            self.record(req, decision)
            return decision

        # 7. Generic Fallback Task Evaluation
        if materiality < req.materiality_threshold and not req.force_refresh:
            decision = ExecutionDecision(
                kind=ExecutionKind.SKIP,
                reason=f"Materiality score ({materiality:.2f}) below threshold ({req.materiality_threshold:.2f}); skipping AI execution.",
                materiality=materiality,
            )
            self.record(req, decision)
            return decision

        tier = "frontier" if materiality >= 0.78 else "balanced" if materiality >= 0.38 else "fast"
        route = self._resolve_route(req, tier)
        decision = ExecutionDecision(
            kind=ExecutionKind.AI,
            reason=f"Task materiality ({materiality:.2f}) exceeds threshold ({req.materiality_threshold:.2f}); routed to {tier} tier.",
            materiality=materiality,
            ai_task_type=task,
            preferred_tier=tier,
            model_route=route,
        )
        self.record(req, decision)
        return decision

    def _resolve_route(
        self,
        req: GateRequest,
        default_tier: str,
        needs_web: bool = False,
        needs_tools: bool = False,
    ) -> ModelDecision:
        route_req = RouteRequest(
            task_type=req.task_type,
            complexity=req.complexity,
            criticality=req.criticality,
            ambiguity=req.ambiguity,
            financial_impact=req.financial_impact,
            needs_tools=req.needs_tools or needs_tools,
            needs_web=req.needs_web or needs_web,
            quality_first=req.quality_first,
            remaining_budget_ratio=req.remaining_budget_ratio,
            allow_empirical_override=req.allow_empirical_override,
            allow_degrade=req.allow_degrade,
            run_id=req.run_id,
        )
        return self.router.decide(route_req)

    def register_cached_result(
        self,
        cache_key: str,
        task_type: Optional[str] = None,
        symbol: Optional[str] = None,
        context_hash: Optional[str] = None,
        result_ref: Optional[str] = None,
    ) -> None:
        """Record that a real, stored reasoning result exists under ``cache_key``.

        Only after this has been called does ``evaluate`` consider the key a
        verified cache hit. This prevents a bare ``cache_key`` field from being
        treated as proof of an actual cached result.
        """
        with sqlite3.connect(self.cfg.db_path) as con:
            con.execute(
                """
                INSERT OR REPLACE INTO cached_results(
                    cache_key, task_type, symbol, context_hash, result_ref, stored_at
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    task_type,
                    symbol.upper() if symbol else None,
                    context_hash,
                    result_ref,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def has_verified_cache(
        self,
        cache_key: str,
        symbol: Optional[str] = None,
        context_hash: Optional[str] = None,
    ) -> bool:
        """True only when a stored result is on record for this cache_key.

        When a symbol/context_hash is supplied they are required to match, so a
        stale key from a different context cannot be treated as a valid hit.
        """
        with sqlite3.connect(self.cfg.db_path) as con:
            row = con.execute(
                """
                SELECT 1 FROM cached_results
                WHERE cache_key = ?
                  AND (? IS NULL OR symbol = ?)
                  AND (? IS NULL OR context_hash = ?)
                LIMIT 1
                """,
                (cache_key, symbol, symbol.upper() if symbol else None, context_hash, context_hash),
            ).fetchone()
        return row is not None

    def record(self, req: GateRequest, decision: ExecutionDecision) -> None:
        with sqlite3.connect(self.cfg.db_path) as con:
            con.execute(
                """
                INSERT INTO execution_gate_decisions(
                    ts, task_type, symbol, kind, materiality, freshness_required,
                    cache_key, preferred_tier, reason, run_id, details_json
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    req.task_type,
                    req.symbol.upper() if req.symbol else None,
                    decision.kind.value,
                    decision.materiality,
                    1 if decision.freshness_required else 0,
                    decision.cache_key,
                    decision.preferred_tier,
                    decision.reason,
                    req.run_id,
                    json.dumps(
                        {
                            "request": req.model_dump(mode="json"),
                            "decision": decision.model_dump(mode="json"),
                        },
                        sort_keys=True,
                    ),
                ),
            )

    def recent_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.cfg.db_path) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                """
                SELECT id, ts, task_type, symbol, kind, materiality, freshness_required,
                       cache_key, preferred_tier, reason, run_id, details_json
                FROM execution_gate_decisions ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["details"] = json.loads(d.pop("details_json"))
            out.append(d)
        return out

    def summary_stats(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        where = "WHERE run_id=?" if run_id else ""
        args = (run_id,) if run_id else ()
        with sqlite3.connect(self.cfg.db_path) as con:
            rows = con.execute(
                f"SELECT kind, COUNT(*) FROM execution_gate_decisions {where} GROUP BY kind",
                args,
            ).fetchall()
        counts = {kind: count for kind, count in rows}
        total = sum(counts.values())
        deterministic = counts.get(ExecutionKind.DETERMINISTIC.value, 0)
        skipped = counts.get(ExecutionKind.SKIP.value, 0)
        cached = counts.get(ExecutionKind.CACHE.value, 0)
        ai_calls = counts.get(ExecutionKind.AI.value, 0)
        ai_avoided = deterministic + skipped + cached
        return {
            "total_decisions": total,
            "deterministic_tasks": deterministic,
            "skipped_tasks": skipped,
            "cached_tasks": cached,
            "ai_tasks": ai_calls,
            "ai_calls_avoided": ai_avoided,
            "ai_avoidance_ratio": (ai_avoided / total) if total > 0 else 0.0,
        }
