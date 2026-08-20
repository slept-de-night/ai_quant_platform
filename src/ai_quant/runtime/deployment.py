from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import sqlite3
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from ..core.config import Settings


class DeploymentStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DISABLED = "disabled"


class DeploymentResolution(BaseModel):
    deployment_id: Optional[int] = None
    requested_tier: str
    resolved_tier: str
    model: str
    status: DeploymentStatus
    fallback_used: bool = False
    reason: str = ""


class RoutingOverride(BaseModel):
    task_type: str
    tier: str
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None
    capital_approved: bool = False
    reason: str = ""


SCHEMA = """
CREATE TABLE IF NOT EXISTS model_deployments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tier TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_model_deployments_tier_active
ON model_deployments(tier, is_active, id DESC);

CREATE TABLE IF NOT EXISTS routing_overrides (
    task_type TEXT PRIMARY KEY,
    tier TEXT NOT NULL,
    model TEXT,
    reasoning_effort TEXT,
    status TEXT NOT NULL DEFAULT 'approved',
    capital_approved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS model_probe_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    deployment_id INTEGER NOT NULL,
    ok INTEGER NOT NULL,
    latency_ms REAL NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS model_health_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    deployment_id INTEGER NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT ''
);
"""


class ModelControlPlane:
    """Versioned model deployments and explicitly approved routing overrides."""

    TIERS = ("fast", "balanced", "frontier")
    FALLBACK = {"frontier": "balanced", "balanced": "fast", "fast": None}

    def __init__(self, cfg: Settings):
        self.cfg = cfg
        with sqlite3.connect(cfg.db_path) as con:
            con.executescript(SCHEMA)
        self.seed_defaults()

    def seed_defaults(self) -> None:
        defaults = {
            "fast": self.cfg.model_fast,
            "balanced": self.cfg.model_balanced,
            "frontier": self.cfg.model_frontier,
        }
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.cfg.db_path) as con:
            for tier, model in defaults.items():
                row = con.execute(
                    "SELECT id FROM model_deployments WHERE tier=? AND is_active=1 ORDER BY id DESC LIMIT 1",
                    (tier,),
                ).fetchone()
                if row:
                    continue
                con.execute(
                    "INSERT INTO model_deployments(tier, model, status, is_active, created_at, approved_at, notes) VALUES(?, ?, ?, ?, ?, ?, ?)",
                    (tier, model, DeploymentStatus.HEALTHY.value, 1, now, now, "seeded from configuration"),
                )

    def list_deployments(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.cfg.db_path) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT id, tier, model, status, is_active, created_at, approved_at, notes FROM model_deployments ORDER BY tier, id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def register_candidate(self, tier: str, model: str, notes: str = "") -> int:
        if tier not in self.TIERS:
            raise ValueError(f"unknown tier: {tier}")
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.cfg.db_path) as con:
            cur = con.execute(
                "INSERT INTO model_deployments(tier, model, status, is_active, created_at, notes) VALUES(?, ?, ?, ?, ?, ?)",
                (tier, model, DeploymentStatus.HEALTHY.value, 0, now, notes),
            )
            return int(cur.lastrowid)

    def activate(self, deployment_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.cfg.db_path) as con:
            row = con.execute("SELECT tier FROM model_deployments WHERE id=?", (deployment_id,)).fetchone()
            if not row:
                raise KeyError(f"deployment {deployment_id} not found")
            tier = row[0]
            con.execute("UPDATE model_deployments SET is_active=0 WHERE tier=?", (tier,))
            con.execute(
                "UPDATE model_deployments SET is_active=1, approved_at=? WHERE id=?",
                (now, deployment_id),
            )

    def set_health(self, deployment_id: int, status: DeploymentStatus, reason: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.cfg.db_path) as con:
            row = con.execute("SELECT status FROM model_deployments WHERE id=?", (deployment_id,)).fetchone()
            if not row:
                raise KeyError(f"deployment {deployment_id} not found")
            old = row[0]
            con.execute("UPDATE model_deployments SET status=? WHERE id=?", (status.value, deployment_id))
            con.execute(
                "INSERT INTO model_health_events(ts, deployment_id, old_status, new_status, reason) VALUES(?, ?, ?, ?, ?)",
                (now, deployment_id, old, status.value, reason),
            )

    def probe(self, deployment_id: int, apply_health: bool = False) -> Dict[str, Any]:
        if not self.cfg.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for a live model probe")
        with sqlite3.connect(self.cfg.db_path) as con:
            row = con.execute("SELECT model, status FROM model_deployments WHERE id=?", (deployment_id,)).fetchone()
        if not row:
            raise KeyError(f"deployment {deployment_id} not found")
        model, _ = row
        from openai import OpenAI
        import time

        started = time.perf_counter()
        err = None
        ok = False
        try:
            r = OpenAI(api_key=self.cfg.openai_api_key).responses.create(
                model=model, reasoning={"effort": "none"}, input="Return exactly: OK"
            )
            ok = bool(getattr(r, "output_text", "").strip())
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
        latency = (time.perf_counter() - started) * 1000
        with sqlite3.connect(self.cfg.db_path) as con:
            con.execute(
                "INSERT INTO model_probe_events(ts, deployment_id, ok, latency_ms, error) VALUES(?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), deployment_id, int(ok), latency, err),
            )
        if apply_health:
            self.set_health(
                deployment_id,
                DeploymentStatus.HEALTHY if ok else DeploymentStatus.DEGRADED,
                err or "probe succeeded",
            )
        return {
            "deployment_id": deployment_id,
            "model": model,
            "ok": ok,
            "latency_ms": latency,
            "error": err,
            "health_changed": apply_health,
        }

    def _active(self, tier: str):
        with sqlite3.connect(self.cfg.db_path) as con:
            return con.execute(
                "SELECT id, model, status FROM model_deployments WHERE tier=? AND is_active=1 ORDER BY id DESC LIMIT 1",
                (tier,),
            ).fetchone()

    def resolve(self, tier: str, allow_degrade: bool = True) -> DeploymentResolution:
        if tier not in self.TIERS:
            raise ValueError(f"unknown tier: {tier}")
        requested = tier
        current = tier
        while current is not None:
            row = self._active(current)
            if row:
                did, model, status_text = row
                status = DeploymentStatus(status_text)
                if status == DeploymentStatus.HEALTHY or (status == DeploymentStatus.DEGRADED and not allow_degrade):
                    return DeploymentResolution(
                        deployment_id=did,
                        requested_tier=requested,
                        resolved_tier=current,
                        model=model,
                        status=status,
                        fallback_used=current != requested,
                        reason="active healthy deployment" if current == requested else f"fallback from {requested}",
                    )
                if status == DeploymentStatus.DEGRADED and allow_degrade:
                    fallback = self.FALLBACK[current]
                    if fallback is None:
                        return DeploymentResolution(
                            deployment_id=did,
                            requested_tier=requested,
                            resolved_tier=current,
                            model=model,
                            status=status,
                            fallback_used=current != requested,
                            reason="degraded deployment used because no lower fallback exists",
                        )
                    current = fallback
                    continue
                if status == DeploymentStatus.DISABLED:
                    current = self.FALLBACK[current]
                    continue
            current = self.FALLBACK[current]

        model = {
            "fast": self.cfg.model_fast,
            "balanced": self.cfg.model_balanced,
            "frontier": self.cfg.model_frontier,
        }[requested]
        return DeploymentResolution(
            requested_tier=requested,
            resolved_tier=requested,
            model=model,
            status=DeploymentStatus.DEGRADED,
            fallback_used=False,
            reason="configuration fallback because deployment registry had no usable entry",
        )

    def get_override(self, task_type: str, financial_impact: float = 0.0) -> Optional[RoutingOverride]:
        with sqlite3.connect(self.cfg.db_path) as con:
            row = con.execute(
                "SELECT task_type, tier, model, reasoning_effort, capital_approved, reason FROM routing_overrides WHERE task_type=? AND status='approved'",
                (task_type,),
            ).fetchone()
        if not row:
            return None
        override = RoutingOverride(
            task_type=row[0],
            tier=row[1],
            model=row[2],
            reasoning_effort=row[3],
            capital_approved=bool(row[4]),
            reason=row[5],
        )
        if financial_impact >= 0.80 and not override.capital_approved:
            return None
        return override

    def approve_override(
        self,
        task_type: str,
        tier: str,
        model: Optional[str],
        reasoning_effort: Optional[str],
        reason: str,
        capital_approved: bool = False,
    ) -> None:
        if tier not in self.TIERS:
            raise ValueError(f"unknown tier: {tier}")
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.cfg.db_path) as con:
            con.execute(
                """
                INSERT INTO routing_overrides(task_type, tier, model, reasoning_effort, status, capital_approved, created_at, approved_at, reason)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_type) DO UPDATE SET
                  tier=excluded.tier, model=excluded.model, reasoning_effort=excluded.reasoning_effort,
                  status='approved', capital_approved=excluded.capital_approved, approved_at=excluded.approved_at, reason=excluded.reason
                """,
                (
                    task_type,
                    tier,
                    model,
                    reasoning_effort,
                    "approved",
                    int(capital_approved),
                    now,
                    now,
                    reason,
                ),
            )

    def clear_override(self, task_type: str) -> None:
        with sqlite3.connect(self.cfg.db_path) as con:
            con.execute("DELETE FROM routing_overrides WHERE task_type=?", (task_type,))
