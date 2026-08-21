from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import sqlite3
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid

from ..core.config import Settings
from .gate import AIExecutionGate, ExecutionDecision, ExecutionKind, GateRequest
from .models import (
    ALLOWED_AGENT_ROLES,
    ALLOWED_TASK_TYPES,
    DelegationRequest,
    RuntimeStatus,
    RuntimeTask,
    TaskNode,
    TaskStatus,
)
from .router import ModelDecision, ModelRouter, RouteRequest

ORCHESTRATOR_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_tasks (
    task_id TEXT PRIMARY KEY,
    root_id TEXT NOT NULL,
    parent_id TEXT,
    created_at TEXT NOT NULL,
    depth INTEGER NOT NULL,
    agent_role TEXT NOT NULL,
    task_type TEXT NOT NULL,
    objective TEXT NOT NULL,
    symbol TEXT,
    estimated_tokens INTEGER NOT NULL,
    status TEXT NOT NULL,
    route_json TEXT,
    depends_json TEXT NOT NULL DEFAULT '[]',
    decision_json TEXT
);

CREATE TABLE IF NOT EXISTS runtime_tasks (
    task_id TEXT PRIMARY KEY,
    root_id TEXT NOT NULL,
    parent_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    task_type TEXT NOT NULL,
    objective TEXT NOT NULL,
    symbol TEXT,
    payload_json TEXT NOT NULL,
    priority INTEGER NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL,
    status TEXT NOT NULL,
    available_at TEXT NOT NULL,
    lease_owner TEXT,
    lease_until TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    output_json TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_runtime_ready ON runtime_tasks(status, available_at, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_runtime_root ON runtime_tasks(root_id, status);

CREATE TABLE IF NOT EXISTS runtime_dependencies (
    task_id TEXT NOT NULL,
    depends_on_task_id TEXT NOT NULL,
    PRIMARY KEY(task_id, depends_on_task_id)
);

CREATE TABLE IF NOT EXISTS runtime_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    task_id TEXT NOT NULL,
    event TEXT NOT NULL,
    worker_id TEXT,
    details_json TEXT NOT NULL
);
"""


class TaskOrchestrator:
    """Bounded delegation control plane."""

    def __init__(
        self,
        cfg: Settings,
        router: Optional[ModelRouter] = None,
        gate: Optional[AIExecutionGate] = None,
    ):
        self.cfg = cfg
        self.router = router or ModelRouter(cfg)
        self.gate = gate or AIExecutionGate(cfg, self.router)
        with sqlite3.connect(cfg.db_path) as con:
            con.executescript(ORCHESTRATOR_SCHEMA)
            cols = {r[1] for r in con.execute("PRAGMA table_info(agent_tasks)").fetchall()}
            if "depends_json" not in cols:
                con.execute("ALTER TABLE agent_tasks ADD COLUMN depends_json TEXT NOT NULL DEFAULT '[]'")
            if "decision_json" not in cols:
                con.execute("ALTER TABLE agent_tasks ADD COLUMN decision_json TEXT")

    def _counts(self, root_id: str, parent_id: Optional[str] = None) -> Tuple[int, int, int]:
        with sqlite3.connect(self.cfg.db_path) as con:
            total = con.execute(
                "SELECT COUNT(*), COALESCE(SUM(estimated_tokens), 0) FROM agent_tasks WHERE root_id=?",
                (root_id,),
            ).fetchone()
            children = (
                con.execute("SELECT COUNT(*) FROM agent_tasks WHERE parent_id=?", (parent_id,)).fetchone()[0]
                if parent_id
                else 0
            )
        return int(total[0]), int(total[1]), int(children)

    def create_root(
        self,
        agent_role: str,
        task_type: str,
        objective: str,
        symbol: Optional[str] = None,
        estimated_tokens: int = 5000,
    ) -> TaskNode:
        tid = str(uuid.uuid4())
        node = TaskNode(
            task_id=tid,
            root_id=tid,
            agent_role=agent_role,
            task_type=task_type,
            objective=objective,
            symbol=symbol,
            estimated_tokens=estimated_tokens,
        )
        self._save(node)
        return node

    def spawn_child(self, parent: TaskNode, request: DelegationRequest) -> TaskNode:
        if request.agent_role not in ALLOWED_AGENT_ROLES:
            raise PermissionError(f"agent role is not approved: {request.agent_role}")
        if request.task_type not in ALLOWED_TASK_TYPES:
            raise PermissionError(f"task type is not approved: {request.task_type}")
        total, tokens, children = self._counts(parent.root_id, parent.task_id)
        if parent.depth + 1 > self.cfg.agent_max_depth:
            raise PermissionError("agent delegation depth limit reached")
        if children >= self.cfg.agent_max_children:
            raise PermissionError("child-task limit reached")
        if total >= self.cfg.agent_max_tasks_per_run:
            raise PermissionError("run task-count budget reached")
        if tokens + request.estimated_tokens > self.cfg.agent_token_budget:
            raise PermissionError("run estimated-token budget reached")

        gate_req = GateRequest(
            task_type=request.task_type,
            symbol=parent.symbol,
            agent_role=request.agent_role,
            objective=request.objective,
            complexity=request.complexity,
            criticality=request.criticality,
            ambiguity=request.ambiguity,
            financial_impact=request.financial_impact,
            needs_web=request.needs_web,
            needs_tools=request.needs_tools,
            quality_first=request.quality_first,
            remaining_budget_ratio=max(
                0.0, 1.0 - (tokens + request.estimated_tokens) / self.cfg.agent_token_budget
            ),
            run_id=parent.root_id,
        )
        decision = self.gate.evaluate(gate_req)
        route = decision.model_route if decision.kind == ExecutionKind.AI else None

        if route and route.tier == "frontier":
            with sqlite3.connect(self.cfg.db_path) as con:
                high = con.execute(
                    "SELECT COUNT(*) FROM agent_tasks WHERE root_id=? AND route_json LIKE '%\"tier\":\"frontier\"%'",
                    (parent.root_id,),
                ).fetchone()[0]
            if high >= self.cfg.agent_max_frontier_tasks and request.financial_impact < 0.85:
                gate_req.criticality = min(gate_req.criticality, 0.55)
                gate_req.complexity = min(gate_req.complexity, 0.60)
                decision = self.gate.evaluate(gate_req)
                route = decision.model_route if decision.kind == ExecutionKind.AI else None

        tid = str(uuid.uuid4())
        node = TaskNode(
            task_id=tid,
            root_id=parent.root_id,
            parent_id=parent.task_id,
            depth=parent.depth + 1,
            agent_role=request.agent_role,
            task_type=request.task_type,
            objective=request.objective,
            symbol=parent.symbol,
            estimated_tokens=request.estimated_tokens,
            route=route,
            execution_decision=decision,
        )
        self._save(node)
        return node

    def _save(self, node: TaskNode):
        with sqlite3.connect(self.cfg.db_path) as con:
            con.execute(
                "INSERT INTO agent_tasks(task_id, root_id, parent_id, created_at, depth, agent_role, task_type, objective, symbol, estimated_tokens, status, route_json, depends_json, decision_json) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    node.task_id,
                    node.root_id,
                    node.parent_id,
                    datetime.now(timezone.utc).isoformat(),
                    node.depth,
                    node.agent_role,
                    node.task_type,
                    node.objective,
                    node.symbol,
                    node.estimated_tokens,
                    node.status.value,
                    node.route.model_dump_json() if node.route else None,
                    json.dumps(node.depends_on),
                    node.execution_decision.model_dump_json()
                    if isinstance(node.execution_decision, ExecutionDecision)
                    else json.dumps(node.execution_decision)
                    if node.execution_decision
                    else None,
                ),
            )

    def plan_research(self, symbol: str) -> List[TaskNode]:
        root = self.create_root(
            "research_manager",
            "research_program",
            f"Build an auditable research dossier for {symbol}",
            symbol,
            4000,
        )
        market = self.spawn_child(
            root,
            DelegationRequest(
                agent_role="market_structure_manager",
                task_type="research_digest",
                objective="Coordinate technical, fundamental, microtrend, and megatrend work",
                complexity=0.45,
                criticality=0.55,
                estimated_tokens=3000,
            ),
        )
        evidence = self.spawn_child(
            root,
            DelegationRequest(
                agent_role="evidence_manager",
                task_type="web_research",
                objective="Coordinate provenance-aware current evidence research",
                complexity=0.65,
                criticality=0.80,
                ambiguity=0.65,
                financial_impact=0.65,
                estimated_tokens=8000,
                needs_web=True,
            ),
        )
        thesis = self.spawn_child(
            root,
            DelegationRequest(
                agent_role="thesis_manager",
                task_type="scenario_synthesis",
                objective="Coordinate future scenarios and falsification",
                complexity=0.82,
                criticality=0.80,
                ambiguity=0.80,
                financial_impact=0.65,
                estimated_tokens=10000,
            ),
        )
        audit = self.spawn_child(
            root,
            DelegationRequest(
                agent_role="audit_agent",
                task_type="critical_review",
                objective="Review evidence, memory freshness, contradictions, and unsupported claims",
                complexity=0.75,
                criticality=0.95,
                ambiguity=0.60,
                financial_impact=0.90,
                estimated_tokens=9000,
                quality_first=False,
            ),
        )

        leaves = [
            self.spawn_child(
                market,
                DelegationRequest(
                    agent_role="technical_agent",
                    task_type="extract",
                    objective="Compute deterministic technical state",
                    complexity=0.20,
                    criticality=0.45,
                    estimated_tokens=1500,
                ),
            ),
            self.spawn_child(
                market,
                DelegationRequest(
                    agent_role="fundamental_agent",
                    task_type="fundamental_review",
                    objective="Analyze point-in-time company fundamentals",
                    complexity=0.55,
                    criticality=0.70,
                    financial_impact=0.45,
                    estimated_tokens=6000,
                ),
            ),
            self.spawn_child(
                market,
                DelegationRequest(
                    agent_role="microtrend_agent",
                    task_type="trend_review",
                    objective="Analyze company/industry relative leadership",
                    complexity=0.50,
                    criticality=0.60,
                    estimated_tokens=4500,
                ),
            ),
            self.spawn_child(
                market,
                DelegationRequest(
                    agent_role="megatrend_agent",
                    task_type="trend_review",
                    objective="Analyze macro and cross-asset regime",
                    complexity=0.60,
                    criticality=0.65,
                    estimated_tokens=5000,
                ),
            ),
            self.spawn_child(
                evidence,
                DelegationRequest(
                    agent_role="web_research_agent",
                    task_type="web_research",
                    objective="Collect current primary/trusted evidence",
                    complexity=0.65,
                    criticality=0.80,
                    ambiguity=0.70,
                    financial_impact=0.50,
                    estimated_tokens=9000,
                    needs_web=True,
                ),
            ),
            self.spawn_child(
                evidence,
                DelegationRequest(
                    agent_role="contradiction_agent",
                    task_type="contradiction",
                    objective="Find material contradictions among sanitized claims",
                    complexity=0.50,
                    criticality=0.80,
                    ambiguity=0.60,
                    financial_impact=0.50,
                    estimated_tokens=5000,
                ),
            ),
            self.spawn_child(
                thesis,
                DelegationRequest(
                    agent_role="future_agent",
                    task_type="scenario_synthesis",
                    objective="Build conditional bull/base/bear scenarios",
                    complexity=0.80,
                    criticality=0.75,
                    ambiguity=0.80,
                    financial_impact=0.55,
                    estimated_tokens=9000,
                ),
            ),
            self.spawn_child(
                thesis,
                DelegationRequest(
                    agent_role="falsification_agent",
                    task_type="falsification",
                    objective="Try to disprove the central hypothesis and define invalidators",
                    complexity=0.85,
                    criticality=0.90,
                    ambiguity=0.80,
                    financial_impact=0.75,
                    estimated_tokens=11000,
                ),
            ),
        ]

        technical, fundamental, micro, mega, web, contradiction, future, falsification = leaves
        contradiction.depends_on = [web.task_id]
        future.depends_on = [market.task_id, evidence.task_id]
        falsification.depends_on = [market.task_id, evidence.task_id]
        audit.depends_on = [market.task_id, evidence.task_id, thesis.task_id]
        for node in [contradiction, future, falsification, audit]:
            with sqlite3.connect(self.cfg.db_path) as con:
                con.execute(
                    "UPDATE agent_tasks SET depends_json=? WHERE task_id=?",
                    (json.dumps(node.depends_on), node.task_id),
                )
        return [root, market, evidence, thesis, audit, *leaves]

    def tree(self, root_id: str) -> List[TaskNode]:
        with sqlite3.connect(self.cfg.db_path) as con:
            rows = con.execute(
                "SELECT task_id, root_id, parent_id, depth, agent_role, task_type, objective, symbol, estimated_tokens, status, route_json, depends_json, decision_json FROM agent_tasks WHERE root_id=? ORDER BY depth, created_at",
                (root_id,),
            ).fetchall()
        return [
            TaskNode(
                task_id=r[0],
                root_id=r[1],
                parent_id=r[2],
                depth=r[3],
                agent_role=r[4],
                task_type=r[5],
                objective=r[6],
                symbol=r[7],
                estimated_tokens=r[8],
                status=TaskStatus(r[9]),
                route=ModelDecision.model_validate_json(r[10]) if r[10] else None,
                depends_on=json.loads(r[11] or "[]"),
                execution_decision=ExecutionDecision.model_validate_json(r[12]) if r[12] else None,
            )
            for r in rows
        ]


class TaskRuntime:
    """Durable SQLite task runtime with distributed-style task leasing."""

    def __init__(self, cfg: Settings):
        self.cfg = cfg
        with sqlite3.connect(cfg.db_path) as con:
            con.executescript(ORCHESTRATOR_SCHEMA)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _event(
        self,
        con,
        task_id: str,
        event: str,
        worker_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        con.execute(
            "INSERT INTO runtime_events(ts, task_id, event, worker_id, details_json) VALUES(?, ?, ?, ?, ?)",
            (self._now().isoformat(), task_id, event, worker_id, json.dumps(details or {}, sort_keys=True)),
        )

    def enqueue(
        self,
        *,
        task_id: Optional[str] = None,
        root_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        agent_role: str,
        task_type: str,
        objective: str,
        symbol: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        priority: int = 100,
        max_attempts: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
    ) -> RuntimeTask:
        now = self._now()
        task_id = task_id or str(uuid.uuid4())
        root_id = root_id or task_id
        payload = payload or {}
        max_attempts = max_attempts or self.cfg.runtime_max_attempts
        if not idempotency_key:
            raw = json.dumps(
                {
                    "root": root_id,
                    "role": agent_role,
                    "type": task_type,
                    "objective": objective,
                    "symbol": symbol,
                    "payload": payload,
                },
                sort_keys=True,
            )
            idempotency_key = hashlib.sha256(raw.encode()).hexdigest()
        with sqlite3.connect(self.cfg.db_path, timeout=30) as con:
            row = con.execute("SELECT task_id FROM runtime_tasks WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if row:
                return self.get(row[0])
            con.execute(
                """
                INSERT INTO runtime_tasks(
                    task_id, root_id, parent_id, created_at, updated_at, agent_role, task_type, objective, symbol,
                    payload_json, priority, attempts, max_attempts, status, available_at, idempotency_key
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    root_id,
                    parent_id,
                    now.isoformat(),
                    now.isoformat(),
                    agent_role,
                    task_type,
                    objective,
                    symbol.upper() if symbol else None,
                    json.dumps(payload, sort_keys=True),
                    priority,
                    0,
                    max_attempts,
                    RuntimeStatus.QUEUED.value,
                    now.isoformat(),
                    idempotency_key,
                ),
            )
            for dep in depends_on or []:
                con.execute(
                    "INSERT OR IGNORE INTO runtime_dependencies(task_id, depends_on_task_id) VALUES(?, ?)",
                    (task_id, dep),
                )
            self._event(con, task_id, "enqueued", details={"depends_on": depends_on or []})
        return self.get(task_id)

    def enqueue_plan(self, nodes: List[TaskNode]) -> List[RuntimeTask]:
        children: Dict[str, List[str]] = {}
        for n in nodes:
            if n.parent_id:
                children.setdefault(n.parent_id, []).append(n.task_id)
        out = []
        for n in reversed(nodes):
            out.append(
                self.enqueue(
                    task_id=n.task_id,
                    root_id=n.root_id,
                    parent_id=n.parent_id,
                    agent_role=n.agent_role,
                    task_type=n.task_type,
                    objective=n.objective,
                    symbol=n.symbol,
                    payload={"route": n.route.model_dump(mode="json") if n.route else None},
                    priority=max(1, 100 - n.depth * 10),
                    idempotency_key=f"plan:{n.task_id}",
                    depends_on=list(dict.fromkeys(children.get(n.task_id, []) + list(n.depends_on))),
                )
            )
        return list(reversed(out))

    def _row(self, r) -> RuntimeTask:
        return RuntimeTask(
            task_id=r[0],
            root_id=r[1],
            parent_id=r[2],
            agent_role=r[3],
            task_type=r[4],
            objective=r[5],
            symbol=r[6],
            payload=json.loads(r[7]),
            priority=r[8],
            attempts=r[9],
            max_attempts=r[10],
            status=RuntimeStatus(r[11]),
            available_at=datetime.fromisoformat(r[12]),
            lease_owner=r[13],
            lease_until=datetime.fromisoformat(r[14]) if r[14] else None,
            idempotency_key=r[15],
            output=json.loads(r[16]) if r[16] else None,
            error=r[17],
        )

    def get(self, task_id: str) -> RuntimeTask:
        with sqlite3.connect(self.cfg.db_path) as con:
            row = con.execute(
                "SELECT task_id, root_id, parent_id, agent_role, task_type, objective, symbol, payload_json, priority, attempts, max_attempts, status, available_at, lease_owner, lease_until, idempotency_key, output_json, error FROM runtime_tasks WHERE task_id=?",
                (task_id,),
            ).fetchone()
        if not row:
            raise KeyError(task_id)
        return self._row(row)

    def _deps_satisfied_sql(self) -> str:
        return """
        NOT EXISTS (
          SELECT 1 FROM runtime_dependencies d
          JOIN runtime_tasks dep ON dep.task_id=d.depends_on_task_id
          WHERE d.task_id=t.task_id AND dep.status!='succeeded'
        )
        """

    def lease(
        self, worker_id: str, limit: int = 1, lease_seconds: Optional[int] = None
    ) -> List[RuntimeTask]:
        lease_seconds = lease_seconds or self.cfg.runtime_lease_seconds
        self.recover_expired()
        now = self._now()
        until = now + timedelta(seconds=lease_seconds)
        claimed: List[str] = []
        with sqlite3.connect(self.cfg.db_path, timeout=30, isolation_level=None) as con:
            con.execute("BEGIN IMMEDIATE")
            rows = con.execute(
                f"""
                SELECT t.task_id FROM runtime_tasks t
                WHERE t.status IN ('queued','retry') AND t.available_at<=? AND {self._deps_satisfied_sql()}
                ORDER BY t.priority DESC, t.created_at ASC
                LIMIT ?
                """,
                (now.isoformat(), limit),
            ).fetchall()
            for (task_id,) in rows:
                cur = con.execute(
                    """
                    UPDATE runtime_tasks
                    SET status='running', attempts=attempts+1, lease_owner=?, lease_until=?, updated_at=?, error=NULL
                    WHERE task_id=? AND status IN ('queued','retry')
                    """,
                    (worker_id, until.isoformat(), now.isoformat(), task_id),
                )
                if cur.rowcount:
                    self._event(con, task_id, "leased", worker_id, {"lease_until": until.isoformat()})
                    claimed.append(task_id)
            con.commit()
        return [self.get(t) for t in claimed]

    def complete(self, task_id: str, worker_id: str, output: Optional[Dict[str, Any]] = None) -> None:
        now = self._now().isoformat()
        with sqlite3.connect(self.cfg.db_path) as con:
            cur = con.execute(
                """
                UPDATE runtime_tasks SET status='succeeded', updated_at=?, lease_owner=NULL, lease_until=NULL,
                    output_json=?, error=NULL
                WHERE task_id=? AND status='running' AND lease_owner=?
                """,
                (now, json.dumps(output or {}, sort_keys=True), task_id, worker_id),
            )
            if cur.rowcount == 0:
                raise PermissionError("worker does not own active lease")
            self._event(con, task_id, "succeeded", worker_id, output or {})

    def fail(
        self, task_id: str, worker_id: str, error: str, retryable: bool = True
    ) -> RuntimeStatus:
        task = self.get(task_id)
        if task.status != RuntimeStatus.RUNNING or task.lease_owner != worker_id:
            raise PermissionError("worker does not own active lease")
        terminal = (not retryable) or task.attempts >= task.max_attempts
        status = RuntimeStatus.DEAD_LETTER if terminal else RuntimeStatus.RETRY
        delay = (
            0
            if terminal
            else min(
                self.cfg.runtime_max_retry_delay_seconds,
                self.cfg.runtime_retry_base_seconds * (2 ** max(0, task.attempts - 1)),
            )
        )
        available = self._now() + timedelta(seconds=delay)
        with sqlite3.connect(self.cfg.db_path) as con:
            con.execute(
                """
                UPDATE runtime_tasks SET status=?, updated_at=?, available_at=?, lease_owner=NULL, lease_until=NULL, error=?
                WHERE task_id=?
                """,
                (status.value, self._now().isoformat(), available.isoformat(), error[:4000], task_id),
            )
            self._event(
                con,
                task_id,
                status.value,
                worker_id,
                {"error": error[:1000], "retry_delay_seconds": delay},
            )
        return status

    def recover_expired(self) -> int:
        now = self._now()
        with sqlite3.connect(self.cfg.db_path, timeout=30) as con:
            rows = con.execute(
                "SELECT task_id, attempts, max_attempts, lease_owner FROM runtime_tasks WHERE status='running' AND lease_until IS NOT NULL AND lease_until<?",
                (now.isoformat(),),
            ).fetchall()
            for task_id, attempts, max_attempts, owner in rows:
                status = RuntimeStatus.DEAD_LETTER if attempts >= max_attempts else RuntimeStatus.RETRY
                con.execute(
                    "UPDATE runtime_tasks SET status=?, available_at=?, lease_owner=NULL, lease_until=NULL, updated_at=?, error=? WHERE task_id=?",
                    (status.value, now.isoformat(), now.isoformat(), "lease expired", task_id),
                )
                self._event(con, task_id, "lease_expired", owner, {"new_status": status.value})
        return len(rows)

    def dependency_outputs(self, task_id: str) -> Dict[str, Dict[str, Any]]:
        with sqlite3.connect(self.cfg.db_path) as con:
            rows = con.execute(
                """
                SELECT dep.task_id, dep.output_json FROM runtime_dependencies d
                JOIN runtime_tasks dep ON dep.task_id=d.depends_on_task_id
                WHERE d.task_id=? AND dep.status='succeeded'
                """,
                (task_id,),
            ).fetchall()
        return {tid: json.loads(out) if out else {} for tid, out in rows}

    def status(self, root_id: Optional[str] = None) -> Dict[str, int]:
        where = "WHERE root_id=?" if root_id else ""
        args = (root_id,) if root_id else ()
        with sqlite3.connect(self.cfg.db_path) as con:
            rows = con.execute(
                f"SELECT status, COUNT(*) FROM runtime_tasks {where} GROUP BY status", args
            ).fetchall()
        return {status: count for status, count in rows}

    def list_tasks(self, root_id: Optional[str] = None, limit: int = 100) -> List[RuntimeTask]:
        where = "WHERE root_id=?" if root_id else ""
        args: list[Any] = [root_id] if root_id else []
        args.append(limit)
        with sqlite3.connect(self.cfg.db_path) as con:
            rows = con.execute(
                f"SELECT task_id, root_id, parent_id, agent_role, task_type, objective, symbol, payload_json, priority, attempts, max_attempts, status, available_at, lease_owner, lease_until, idempotency_key, output_json, error FROM runtime_tasks {where} ORDER BY priority DESC, task_id LIMIT ?",
                args,
            ).fetchall()
        return [self._row(r) for r in rows]

    def events(self, task_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        where = "WHERE task_id=?" if task_id else ""
        args: list[Any] = [task_id] if task_id else []
        args.append(limit)
        with sqlite3.connect(self.cfg.db_path) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                f"SELECT id, ts, task_id, event, worker_id, details_json FROM runtime_events {where} ORDER BY id DESC LIMIT ?",
                args,
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["details"] = json.loads(d.pop("details_json"))
            out.append(d)
        return out


Handler = Callable[[RuntimeTask, Dict[str, Dict[str, Any]]], Dict[str, Any]]


class WorkerPool:
    """Worker pool for executing leased tasks concurrently."""

    def __init__(
        self,
        runtime: TaskRuntime,
        handlers: Dict[str, Handler],
        worker_prefix: str = "local",
    ):
        self.runtime = runtime
        self.handlers = handlers
        self.worker_prefix = worker_prefix

    def _run_task(self, task: RuntimeTask, worker_id: str) -> Tuple[str, RuntimeStatus]:
        handler = self.handlers.get(task.task_type)
        if handler is None:
            status = self.runtime.fail(
                task.task_id, worker_id, f"no handler for {task.task_type}", retryable=False
            )
            return task.task_id, status
        try:
            deps = self.runtime.dependency_outputs(task.task_id)
            output = handler(task, deps)
            if not isinstance(output, dict):
                output = {"result": output}
            self.runtime.complete(task.task_id, worker_id, output)
            return task.task_id, RuntimeStatus.SUCCEEDED
        except Exception as exc:
            status = self.runtime.fail(
                task.task_id, worker_id, f"{type(exc).__name__}: {exc}", retryable=True
            )
            return task.task_id, status

    def run_once(self, concurrency: Optional[int] = None) -> List[Tuple[str, RuntimeStatus]]:
        concurrency = concurrency or self.runtime.cfg.runtime_concurrency
        worker_id = f"{self.worker_prefix}-{uuid.uuid4().hex[:8]}"
        leased = self.runtime.lease(worker_id, limit=concurrency)
        if not leased:
            return []
        results = []
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = [ex.submit(self._run_task, t, worker_id) for t in leased]
            for fut in as_completed(futs):
                results.append(fut.result())
        return results

    def run_until_idle(
        self, concurrency: Optional[int] = None, max_cycles: int = 100
    ) -> List[Tuple[str, RuntimeStatus]]:
        all_results = []
        for _ in range(max_cycles):
            batch = self.run_once(concurrency)
            if not batch:
                break
            all_results.extend(batch)
        return all_results
