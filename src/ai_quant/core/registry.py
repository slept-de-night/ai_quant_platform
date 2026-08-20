from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Tuple

from .models import StrategySpec, StrategyStatus, ValidationReport

SCHEMA = """
CREATE TABLE IF NOT EXISTS strategies (
    name TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    spec_json TEXT NOT NULL,
    validation_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    passed INTEGER NOT NULL,
    robust_score REAL NOT NULL,
    validation_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    ts TEXT PRIMARY KEY,
    equity REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS order_log (
    client_order_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    side TEXT NOT NULL,
    qty INTEGER NOT NULL,
    status TEXT NOT NULL,
    broker_order_id TEXT
);

CREATE TABLE IF NOT EXISTS research_dossiers (
    symbol TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    dossier_json TEXT NOT NULL
);
"""


class Registry:
    def __init__(self, path: str):
        self.path = path
        with sqlite3.connect(path) as conn:
            conn.executescript(SCHEMA)

    def upsert_strategy(
        self,
        spec: StrategySpec,
        status: StrategyStatus = StrategyStatus.CANDIDATE,
        report: Optional[ValidationReport] = None,
    ):
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO strategies(name, status, spec_json, validation_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    status=excluded.status,
                    spec_json=excluded.spec_json,
                    validation_json=excluded.validation_json,
                    updated_at=excluded.updated_at
                """,
                (
                    spec.name,
                    status.value,
                    spec.model_dump_json(),
                    report.model_dump_json() if report else None,
                    now,
                    now,
                ),
            )

    def record_experiment(self, symbol: str, spec: StrategySpec, report: ValidationReport):
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO experiments(ts, symbol, strategy_name, passed, robust_score, validation_json)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    symbol,
                    spec.name,
                    int(report.passed),
                    report.robust_score,
                    report.model_dump_json(),
                ),
            )

    def approve(self, name: str):
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT status FROM strategies WHERE name=?", (name,)).fetchone()
            if not row:
                raise KeyError(name)
            if row[0] != StrategyStatus.VALIDATED.value:
                raise PermissionError(f"Strategy {name} is {row[0]}; only validated strategies may be approved")
            conn.execute(
                "UPDATE strategies SET status=?, updated_at=? WHERE name=?",
                (StrategyStatus.APPROVED.value, datetime.now(timezone.utc).isoformat(), name),
            )

    def get(self, name: str, require_approved: bool = False) -> Tuple[StrategySpec, StrategyStatus]:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT status, spec_json FROM strategies WHERE name=?", (name,)).fetchone()
        if not row:
            raise KeyError(name)
        if require_approved and row[0] != StrategyStatus.APPROVED.value:
            raise PermissionError(f"Strategy {name} is {row[0]}, not approved")
        return StrategySpec.model_validate_json(row[1]), StrategyStatus(row[0])

    def list_strategies(self) -> List[Tuple[str, str, str]]:
        with sqlite3.connect(self.path) as conn:
            return conn.execute("SELECT name, status, updated_at FROM strategies ORDER BY status, name").fetchall()

    def memory_summary(self, limit: int = 20) -> str:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT strategy_name, passed, robust_score FROM experiments ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return "; ".join(f"{n}: {'PASS' if p else 'FAIL'} robust={s:.2f}" for n, p, s in rows)

    def observe_equity(self, equity: float):
        ts = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT INTO account_snapshots(ts, equity) VALUES(?, ?)", (ts, equity))

    def peak_equity(self, current: float) -> float:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT MAX(equity) FROM account_snapshots").fetchone()
        return max(current, float(row[0])) if row and row[0] is not None else current

    def daily_start_equity(self, current: float) -> float:
        today = datetime.now(timezone.utc).date().isoformat()
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT equity FROM account_snapshots WHERE substr(ts, 1, 10)=? ORDER BY ts LIMIT 1",
                (today,),
            ).fetchone()
        return float(row[0]) if row else current

    def order_exists(self, client_order_id: str) -> bool:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT 1 FROM order_log WHERE client_order_id=?", (client_order_id,)).fetchone()
            return row is not None

    def reserve_order(self, order: Any) -> bool:
        try:
            with sqlite3.connect(self.path) as conn:
                conn.execute(
                    """
                    INSERT INTO order_log(client_order_id, ts, symbol, strategy_name, side, qty, status)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order.client_order_id,
                        datetime.now(timezone.utc).isoformat(),
                        order.symbol,
                        order.strategy_name,
                        order.side.value if hasattr(order.side, "value") else str(order.side),
                        order.qty,
                        "reserved",
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def mark_order(self, client_order_id: str, status: str, broker_order_id: Optional[str] = None):
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "UPDATE order_log SET status=?, broker_order_id=? WHERE client_order_id=?",
                (status, broker_order_id, client_order_id),
            )

    def save_dossier(self, dossier: Any):
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO research_dossiers(symbol, generated_at, expires_at, dossier_json)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    generated_at=excluded.generated_at,
                    expires_at=excluded.expires_at,
                    dossier_json=excluded.dossier_json
                """,
                (
                    dossier.symbol.upper(),
                    dossier.generated_at.isoformat(),
                    dossier.expires_at.isoformat(),
                    dossier.model_dump_json(),
                ),
            )

    def get_dossier(self, symbol: str, require_fresh: bool = True) -> Optional[Any]:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT expires_at, dossier_json FROM research_dossiers WHERE symbol=?",
                (symbol.upper(),),
            ).fetchone()
        if not row:
            return None

        # Deferred import to avoid circular references
        from ..intelligence.models import ResearchDossier
        dossier = ResearchDossier.model_validate_json(row[1])
        if require_fresh:
            expires_at = datetime.fromisoformat(row[0])
            if datetime.now(timezone.utc) > expires_at:
                return None
        return dossier
