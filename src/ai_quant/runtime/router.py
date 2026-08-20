from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from typing import Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from ..core.config import Settings
from .deployment import ModelControlPlane


class RouteRequest(BaseModel):
    task_type: str
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


class ModelDecision(BaseModel):
    task_type: str
    tier: str
    requested_tier: Optional[str] = None
    model: str
    deployment_id: Optional[int] = None
    reasoning_effort: str
    reasoning_mode: str = "standard"
    score: float
    policy_source: str = "heuristic"
    fallback_used: bool = False
    reason: str


SCHEMA = """
CREATE TABLE IF NOT EXISTS model_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    task_type TEXT NOT NULL,
    request_json TEXT NOT NULL,
    decision_json TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    response_id TEXT,
    latency_ms REAL,
    error TEXT,
    run_id TEXT,
    estimated_cost_usd REAL
);
"""


class ModelRouter:
    """Policy router with versioned deployments and explicitly approved empirical overrides."""

    def __init__(self, cfg: Settings, control: Optional[ModelControlPlane] = None):
        self.cfg = cfg
        self.control = control or ModelControlPlane(cfg)
        with sqlite3.connect(cfg.db_path) as con:
            con.executescript(SCHEMA)
            cols = {r[1] for r in con.execute("PRAGMA table_info(model_routes)").fetchall()}
            if "latency_ms" not in cols:
                con.execute("ALTER TABLE model_routes ADD COLUMN latency_ms REAL")
            if "error" not in cols:
                con.execute("ALTER TABLE model_routes ADD COLUMN error TEXT")
            if "run_id" not in cols:
                con.execute("ALTER TABLE model_routes ADD COLUMN run_id TEXT")
            if "estimated_cost_usd" not in cols:
                con.execute("ALTER TABLE model_routes ADD COLUMN estimated_cost_usd REAL")

    def _heuristic(self, req: RouteRequest) -> Tuple[str, str, float, str]:
        score = 0.40 * req.complexity + 0.30 * req.criticality + 0.15 * req.ambiguity + 0.15 * req.financial_impact
        task = req.task_type.lower()
        cheap_types = {
            "extract",
            "classify",
            "format",
            "summarize_notes",
            "journal",
            "deduplicate",
            "source_tier",
        }
        balanced_types = {
            "web_research",
            "fundamental_review",
            "trend_review",
            "contradiction",
            "research_digest",
        }
        frontier_types = {
            "hypothesis",
            "falsification",
            "alpha_generation",
            "scenario_synthesis",
            "critical_review",
            "promotion_review",
        }

        if task in cheap_types and score < 0.72:
            tier = "fast"
        elif task in frontier_types and score >= 0.55:
            tier = "frontier"
        elif task in balanced_types and score < 0.82:
            tier = "balanced"
        elif score >= 0.78:
            tier = "frontier"
        elif score >= 0.38:
            tier = "balanced"
        else:
            tier = "fast"

        if req.remaining_budget_ratio < 0.15 and req.financial_impact < 0.70:
            tier = {"frontier": "balanced", "balanced": "fast", "fast": "fast"}[tier]

        if tier == "fast":
            effort = "low" if (req.needs_tools or req.needs_web or score > 0.25) else "none"
        elif tier == "balanced":
            effort = "medium" if score < 0.72 else "high"
        else:
            effort = "high" if score < 0.90 else "xhigh"

        mode = "standard"
        if req.quality_first and tier == "frontier" and score >= 0.93:
            effort = "max"
            mode = "pro" if self.cfg.enable_pro_mode else "standard"
        return tier, effort, score, mode

    def decide(self, req: RouteRequest) -> ModelDecision:
        tier, effort, score, mode = self._heuristic(req)
        requested_tier = tier
        policy_source = "heuristic"
        explicit_model = None

        if req.allow_empirical_override:
            override = self.control.get_override(req.task_type, req.financial_impact)
            if override is not None:
                tier = override.tier
                explicit_model = override.model
                effort = override.reasoning_effort or effort
                policy_source = "approved_empirical_override"

        resolution = self.control.resolve(tier, allow_degrade=req.allow_degrade)
        model = explicit_model or resolution.model
        reason = (
            f"score={score:.2f}; requested={requested_tier}; tier={resolution.resolved_tier}; "
            f"task={req.task_type}; budget={req.remaining_budget_ratio:.2f}; source={policy_source}"
        )
        if resolution.fallback_used:
            reason += f"; deployment_fallback={resolution.reason}"

        return ModelDecision(
            task_type=req.task_type,
            tier=resolution.resolved_tier,
            requested_tier=requested_tier,
            model=model,
            deployment_id=resolution.deployment_id,
            reasoning_effort=effort,
            reasoning_mode=mode,
            score=score,
            policy_source=policy_source,
            fallback_used=resolution.fallback_used,
            reason=reason,
        )

    def _estimate_cost(
        self,
        decision: ModelDecision,
        input_tokens: Optional[int],
        output_tokens: Optional[int],
    ) -> float:
        rates = {
            "fast": (self.cfg.model_fast_input_usd_per_m, self.cfg.model_fast_output_usd_per_m),
            "balanced": (self.cfg.model_balanced_input_usd_per_m, self.cfg.model_balanced_output_usd_per_m),
            "frontier": (self.cfg.model_frontier_input_usd_per_m, self.cfg.model_frontier_output_usd_per_m),
        }
        inp, out = rates.get(decision.tier, (0.0, 0.0))
        return ((input_tokens or 0) / 1_000_000) * inp + ((output_tokens or 0) / 1_000_000) * out

    def spend_for_run(self, run_id: str) -> float:
        with sqlite3.connect(self.cfg.db_path) as con:
            row = con.execute(
                "SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM model_routes WHERE run_id=?",
                (run_id,),
            ).fetchone()
        return float(row[0] or 0.0)

    def _ensure_budget(self, req: RouteRequest) -> None:
        if not req.run_id or self.cfg.agent_usd_budget_per_run <= 0:
            return
        spent = self.spend_for_run(req.run_id)
        if spent >= self.cfg.agent_usd_budget_per_run:
            raise RuntimeError(
                f"AI run budget exhausted for {req.run_id}: ${spent:.4f} >= ${self.cfg.agent_usd_budget_per_run:.4f}"
            )

    def record(
        self,
        req: RouteRequest,
        decision: ModelDecision,
        response=None,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None,
    ):
        inp = out = None
        rid = None
        if response is not None:
            rid = getattr(response, "id", None)
            usage = getattr(response, "usage", None)
            if usage is not None:
                inp = getattr(usage, "input_tokens", None)
                out = getattr(usage, "output_tokens", None)
        cost = self._estimate_cost(decision, inp, out)
        with sqlite3.connect(self.cfg.db_path) as con:
            con.execute(
                "INSERT INTO model_routes(ts, task_type, request_json, decision_json, input_tokens, output_tokens, response_id, latency_ms, error, run_id, estimated_cost_usd) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    req.task_type,
                    req.model_dump_json(),
                    decision.model_dump_json(),
                    inp,
                    out,
                    rid,
                    latency_ms,
                    error,
                    req.run_id,
                    cost,
                ),
            )

    def parse(self, req: RouteRequest, *, input, text_format):
        if not self.cfg.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        from openai import OpenAI
        import time

        self._ensure_budget(req)
        d = self.decide(req)
        client = OpenAI(api_key=self.cfg.openai_api_key)
        reasoning = {"effort": d.reasoning_effort}
        if d.reasoning_mode == "pro":
            reasoning["mode"] = "pro"
        started = time.perf_counter()
        try:
            r = client.responses.parse(
                model=d.model,
                reasoning=reasoning,
                input=input,
                text_format=text_format,
            )
        except Exception as exc:
            self.record(
                req,
                d,
                latency_ms=(time.perf_counter() - started) * 1000,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        self.record(req, d, r, latency_ms=(time.perf_counter() - started) * 1000)
        return r, d

    def create(self, req: RouteRequest, *, input, tools=None, tool_choice=None, include=None):
        if not self.cfg.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        from openai import OpenAI
        import time

        self._ensure_budget(req)
        d = self.decide(req)
        client = OpenAI(api_key=self.cfg.openai_api_key)
        kwargs = {
            "model": d.model,
            "reasoning": {"effort": d.reasoning_effort},
            "input": input,
        }
        if d.reasoning_mode == "pro":
            kwargs["reasoning"]["mode"] = "pro"
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        if include is not None:
            kwargs["include"] = include
        started = time.perf_counter()
        try:
            r = client.responses.create(**kwargs)
        except Exception as exc:
            self.record(
                req,
                d,
                latency_ms=(time.perf_counter() - started) * 1000,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        self.record(req, d, r, latency_ms=(time.perf_counter() - started) * 1000)
        return r, d

    def recent_routes(self, limit: int = 30) -> List[Tuple[Any, ...]]:
        with sqlite3.connect(self.cfg.db_path) as con:
            return con.execute(
                "SELECT ts, task_type, decision_json, input_tokens, output_tokens, latency_ms, error, run_id, estimated_cost_usd FROM model_routes ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
