from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ..core.config import Settings
from .deployment import ModelControlPlane


class TaskEvaluation(BaseModel):
    task_id: Optional[str] = None
    task_type: str
    model: str
    tier: str
    success: bool
    quality_score: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    evaluator: str = "system"
    notes: str = ""


class RoutingRecommendation(BaseModel):
    id: Optional[int] = None
    task_type: str
    current_tier: str
    recommended_tier: str
    recommended_model: str
    recommended_effort: str
    sample_count: int
    expected_utility: float
    reason: str
    status: str = "proposed"


SCHEMA = """
CREATE TABLE IF NOT EXISTS task_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    task_id TEXT,
    task_type TEXT NOT NULL,
    model TEXT NOT NULL,
    tier TEXT NOT NULL,
    success INTEGER NOT NULL,
    quality_score REAL NOT NULL,
    evidence_score REAL NOT NULL,
    latency_ms REAL NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    evaluator TEXT NOT NULL,
    notes TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_evals_type_model ON task_evaluations(task_type, model, id DESC);

CREATE TABLE IF NOT EXISTS routing_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    task_type TEXT NOT NULL,
    current_tier TEXT NOT NULL,
    recommended_tier TEXT NOT NULL,
    recommended_model TEXT NOT NULL,
    recommended_effort TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    expected_utility REAL NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    reviewed_at TEXT,
    capital_approved INTEGER NOT NULL DEFAULT 0
);
"""


class EvaluationManager:
    """Measures task/model outcomes and proposes empirical routing improvements."""

    def __init__(self, cfg: Settings, control: Optional[ModelControlPlane] = None):
        self.cfg = cfg
        self.control = control or ModelControlPlane(cfg)
        with sqlite3.connect(cfg.db_path) as con:
            con.executescript(SCHEMA)

    def estimate_cost(self, tier: str, input_tokens: int, output_tokens: int) -> float:
        rates = {
            "fast": (self.cfg.model_fast_input_usd_per_m, self.cfg.model_fast_output_usd_per_m),
            "balanced": (self.cfg.model_balanced_input_usd_per_m, self.cfg.model_balanced_output_usd_per_m),
            "frontier": (self.cfg.model_frontier_input_usd_per_m, self.cfg.model_frontier_output_usd_per_m),
        }
        inp, out = rates.get(tier, (0.0, 0.0))
        return (input_tokens / 1_000_000) * inp + (output_tokens / 1_000_000) * out

    def record(self, evaluation: TaskEvaluation) -> int:
        if evaluation.cost_usd == 0.0 and (evaluation.input_tokens or evaluation.output_tokens):
            evaluation.cost_usd = self.estimate_cost(
                evaluation.tier, evaluation.input_tokens, evaluation.output_tokens
            )
        with sqlite3.connect(self.cfg.db_path) as con:
            cur = con.execute(
                """
                INSERT INTO task_evaluations(
                    ts, task_id, task_type, model, tier, success, quality_score, evidence_score,
                    latency_ms, input_tokens, output_tokens, cost_usd, evaluator, notes
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    evaluation.task_id,
                    evaluation.task_type,
                    evaluation.model,
                    evaluation.tier,
                    int(evaluation.success),
                    evaluation.quality_score,
                    evaluation.evidence_score,
                    evaluation.latency_ms,
                    evaluation.input_tokens,
                    evaluation.output_tokens,
                    evaluation.cost_usd,
                    evaluation.evaluator,
                    evaluation.notes,
                ),
            )
            return int(cur.lastrowid)

    def performance(self, task_type: Optional[str] = None, min_samples: int = 1) -> List[Dict[str, Any]]:
        where = ""
        args: list = []
        if task_type:
            where = "WHERE task_type=?"
            args.append(task_type)
        sql = f"""
        SELECT task_type, model, tier, COUNT(*) n, AVG(success) success_rate,
               AVG(quality_score) quality, AVG(evidence_score) evidence,
               AVG(latency_ms) latency_ms, AVG(cost_usd) avg_cost,
               SUM(input_tokens) input_tokens, SUM(output_tokens) output_tokens
        FROM task_evaluations
        {where}
        GROUP BY task_type, model, tier
        HAVING COUNT(*)>=?
        ORDER BY task_type, quality DESC, success_rate DESC
        """
        args.append(min_samples)
        with sqlite3.connect(self.cfg.db_path) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def _utility(self, row: dict, max_cost: float, max_latency: float) -> float:
        cost_pen = 0.0 if max_cost <= 0 else row["avg_cost"] / max_cost
        lat_pen = 0.0 if max_latency <= 0 else row["latency_ms"] / max_latency
        return (
            0.45 * float(row["quality"])
            + 0.30 * float(row["success_rate"])
            + 0.15 * float(row["evidence"])
            - 0.06 * cost_pen
            - 0.04 * lat_pen
        )

    def recommend(
        self, task_type: str, current_tier: str, min_samples: Optional[int] = None
    ) -> Optional[RoutingRecommendation]:
        min_samples = min_samples or self.cfg.router_learning_min_samples
        rows = self.performance(task_type=task_type, min_samples=min_samples)
        if len(rows) < 1:
            return None
        max_cost = max(float(r["avg_cost"]) for r in rows) or 0.0
        max_latency = max(float(r["latency_ms"]) for r in rows) or 0.0
        scored = [(self._utility(r, max_cost, max_latency), r) for r in rows]
        scored.sort(key=lambda x: x[0], reverse=True)
        utility, best = scored[0]

        if (
            best["quality"] < self.cfg.router_learning_min_quality
            or best["success_rate"] < self.cfg.router_learning_min_success
        ):
            return None

        effort = "low" if best["tier"] == "fast" else "medium" if best["tier"] == "balanced" else "high"
        reason = (
            f"empirical n={best['n']}; success={best['success_rate']:.2f}; quality={best['quality']:.2f}; "
            f"evidence={best['evidence']:.2f}; avg_cost=${best['avg_cost']:.6f}; latency={best['latency_ms']:.0f}ms"
        )
        rec = RoutingRecommendation(
            task_type=task_type,
            current_tier=current_tier,
            recommended_tier=best["tier"],
            recommended_model=best["model"],
            recommended_effort=effort,
            sample_count=int(best["n"]),
            expected_utility=float(utility),
            reason=reason,
        )
        with sqlite3.connect(self.cfg.db_path) as con:
            cur = con.execute(
                """
                INSERT INTO routing_recommendations(
                  created_at, task_type, current_tier, recommended_tier, recommended_model, recommended_effort,
                  sample_count, expected_utility, reason, status
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    rec.task_type,
                    rec.current_tier,
                    rec.recommended_tier,
                    rec.recommended_model,
                    rec.recommended_effort,
                    rec.sample_count,
                    rec.expected_utility,
                    rec.reason,
                    rec.status,
                ),
            )
            rec.id = int(cur.lastrowid)
        return rec

    def list_recommendations(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        where = "WHERE status=?" if status else ""
        args = [status] if status else []
        with sqlite3.connect(self.cfg.db_path) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(f"SELECT * FROM routing_recommendations {where} ORDER BY id DESC", args).fetchall()
        return [dict(r) for r in rows]

    def approve(self, recommendation_id: int, capital_approved: bool = False) -> RoutingRecommendation:
        with sqlite3.connect(self.cfg.db_path) as con:
            row = con.execute(
                "SELECT id, task_type, current_tier, recommended_tier, recommended_model, recommended_effort, sample_count, expected_utility, reason, status FROM routing_recommendations WHERE id=?",
                (recommendation_id,),
            ).fetchone()
            if not row:
                raise KeyError(f"routing recommendation {recommendation_id} not found")
            rec = RoutingRecommendation(
                id=row[0],
                task_type=row[1],
                current_tier=row[2],
                recommended_tier=row[3],
                recommended_model=row[4],
                recommended_effort=row[5],
                sample_count=row[6],
                expected_utility=row[7],
                reason=row[8],
                status=row[9],
            )
            now = datetime.now(timezone.utc).isoformat()
            con.execute(
                "UPDATE routing_recommendations SET status='approved', reviewed_at=?, capital_approved=? WHERE id=?",
                (now, int(capital_approved), recommendation_id),
            )
        self.control.approve_override(
            task_type=rec.task_type,
            tier=rec.recommended_tier,
            model=rec.recommended_model,
            reasoning_effort=rec.recommended_effort,
            reason=f"approved recommendation #{recommendation_id}: {rec.reason}",
            capital_approved=capital_approved,
        )
        rec.status = "approved"
        return rec

    def reject(self, recommendation_id: int) -> None:
        with sqlite3.connect(self.cfg.db_path) as con:
            cur = con.execute(
                "UPDATE routing_recommendations SET status='rejected', reviewed_at=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), recommendation_id),
            )
            if cur.rowcount == 0:
                raise KeyError(f"routing recommendation {recommendation_id} not found")
