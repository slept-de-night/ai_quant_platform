from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import json
import sqlite3
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .memory_graph import (
    ClaimDirection,
    Contradiction,
    calculate_decayed_confidence,
    classify_claim_direction,
    compute_text_similarity,
    detect_contradictions,
    extract_entities,
)


class MemoryKind(str, Enum):
    OBSERVATION = "observation"
    LESSON = "lesson"
    TIP = "tip"
    HYPOTHESIS = "hypothesis"
    FAILURE = "failure"
    DECISION = "decision"
    WARNING = "warning"


class MemoryNote(BaseModel):
    id: Optional[int] = None
    agent: str
    kind: MemoryKind
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    as_of_date: Optional[datetime] = None
    point_in_time: Optional[datetime] = None
    decision_id: Optional[str] = None
    claim_direction: Optional[ClaimDirection] = None
    symbol: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    entities: Dict[str, List[str]] = Field(default_factory=dict)
    expires_at: Optional[datetime] = None
    supersedes_id: Optional[int] = None
    status: str = "active"


SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS agent_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    agent TEXT NOT NULL,
    kind TEXT NOT NULL,
    symbol TEXT,
    content TEXT NOT NULL,
    confidence REAL NOT NULL,
    importance REAL NOT NULL,
    tags_json TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    expires_at TEXT,
    supersedes_id INTEGER,
    status TEXT NOT NULL DEFAULT 'active',
    as_of_date TEXT,
    point_in_time TEXT,
    decision_id TEXT,
    claim_direction TEXT,
    entities_json TEXT
);
"""

SCHEMA_INDICES = """
CREATE INDEX IF NOT EXISTS idx_agent_memory_agent_time ON agent_memory(agent, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_memory_symbol_time ON agent_memory(symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_memory_decision ON agent_memory(decision_id);
"""


class AgentMemoryStore:
    """
    Append-first agent memory intelligence store.
    SQLite is the source of truth with structured entity indexing and graph capabilities.
    """

    def __init__(self, db_path: str, markdown_dir: str = "agent_memory"):
        self.db_path = db_path
        self.markdown_dir = Path(markdown_dir)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.executescript(SCHEMA_TABLE)
            # Ensure schema migration for newly added columns if table already existed
            cursor = con.execute("PRAGMA table_info(agent_memory)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            for col, col_type in [
                ("as_of_date", "TEXT"),
                ("point_in_time", "TEXT"),
                ("decision_id", "TEXT"),
                ("claim_direction", "TEXT"),
                ("entities_json", "TEXT"),
            ]:
                if col not in existing_cols:
                    con.execute(f"ALTER TABLE agent_memory ADD COLUMN {col} {col_type}")
            # Create indices after columns are guaranteed to exist
            con.executescript(SCHEMA_INDICES)

    def add(self, note: MemoryNote) -> MemoryNote:
        # Automatic entity and claim direction enrichment if missing
        if not note.entities:
            note.entities = extract_entities(note.content, note.symbol)
        if not note.claim_direction:
            note.claim_direction = classify_claim_direction(note.content)
        if not note.as_of_date:
            note.as_of_date = note.created_at
        if not note.point_in_time:
            note.point_in_time = note.created_at

        if note.supersedes_id is not None:
            with sqlite3.connect(self.db_path) as con:
                row = con.execute("SELECT id FROM agent_memory WHERE id=?", (note.supersedes_id,)).fetchone()
                if not row:
                    raise KeyError(f"Cannot supersede missing memory note {note.supersedes_id}")
                con.execute("UPDATE agent_memory SET status='superseded' WHERE id=?", (note.supersedes_id,))

        with sqlite3.connect(self.db_path) as con:
            cur = con.execute(
                """
                INSERT INTO agent_memory(
                    created_at, agent, kind, symbol, content, confidence, importance,
                    tags_json, sources_json, expires_at, supersedes_id, status,
                    as_of_date, point_in_time, decision_id, claim_direction, entities_json
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note.created_at.astimezone(timezone.utc).isoformat(),
                    note.agent,
                    note.kind.value,
                    note.symbol.upper() if note.symbol else None,
                    note.content.strip(),
                    note.confidence,
                    note.importance,
                    json.dumps(note.tags),
                    json.dumps(note.sources),
                    note.expires_at.astimezone(timezone.utc).isoformat() if note.expires_at else None,
                    note.supersedes_id,
                    note.status,
                    note.as_of_date.astimezone(timezone.utc).isoformat() if note.as_of_date else None,
                    note.point_in_time.astimezone(timezone.utc).isoformat() if note.point_in_time else None,
                    note.decision_id,
                    note.claim_direction.value if note.claim_direction else None,
                    json.dumps(note.entities),
                ),
            )
            note.id = int(cur.lastrowid)
        self.render_agent(note.agent)
        return note

    def add_with_hygiene(
        self,
        note: MemoryNote,
        dedup_threshold: float = 0.85,
        detect_conflicts: bool = True,
    ) -> Dict[str, Any]:
        """
        Appends memory with automated deduplication and contradiction analysis.
        """
        # 1. Check for duplicates
        duplicates = self.find_duplicates(note.content, symbol=note.symbol, threshold=dedup_threshold)
        if duplicates:
            return {
                "action": "duplicate_skipped",
                "note": duplicates[0],
                "duplicate_of_id": duplicates[0].id,
                "similarity": compute_text_similarity(note.content, duplicates[0].content),
                "contradictions": [],
            }

        # 2. Check for contradictions against active notes
        contradictions: List[Contradiction] = []
        if detect_conflicts:
            active_notes = self.list_notes(symbol=note.symbol, active_only=True, limit=50)
            contradictions = detect_contradictions(note.content, note.symbol, note.confidence, active_notes)

        # 3. Add to store
        saved_note = self.add(note)

        return {
            "action": "added",
            "note": saved_note,
            "duplicate_of_id": None,
            "contradictions": contradictions,
        }

    def find_duplicates(
        self,
        content: str,
        symbol: Optional[str] = None,
        threshold: float = 0.85,
    ) -> List[MemoryNote]:
        """
        Searches active notes for high textual similarity to avoid polluting memory.
        """
        candidates = self.list_notes(symbol=symbol, active_only=True, limit=50)
        duplicates = []
        for note in candidates:
            sim = compute_text_similarity(content, note.content)
            if sim >= threshold:
                duplicates.append(note)
        return duplicates

    def get_audit_trail(self, decision_id: str) -> List[MemoryNote]:
        """Retrieves all memory notes attached to a decision ID for audit trail verification."""
        with sqlite3.connect(self.db_path) as con:
            rows = con.execute(
                """
                SELECT id, created_at, agent, kind, symbol, content, confidence, importance,
                       tags_json, sources_json, expires_at, supersedes_id, status,
                       as_of_date, point_in_time, decision_id, claim_direction, entities_json
                FROM agent_memory
                WHERE decision_id=?
                ORDER BY created_at ASC, id ASC
                """,
                (decision_id,),
            ).fetchall()
        return [self._row(r) for r in rows]

    def list_notes(
        self,
        agent: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100,
        active_only: bool = False,
    ) -> List[MemoryNote]:
        where = []
        args = []
        if agent:
            where.append("agent=?")
            args.append(agent)
        if symbol:
            where.append("symbol=?")
            args.append(symbol.upper())
        if active_only:
            where.append("status='active'")
            where.append("(expires_at IS NULL OR expires_at>?)")
            args.append(datetime.now(timezone.utc).isoformat())

        sql = """
        SELECT id, created_at, agent, kind, symbol, content, confidence, importance,
               tags_json, sources_json, expires_at, supersedes_id, status,
               as_of_date, point_in_time, decision_id, claim_direction, entities_json
        FROM agent_memory
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        args.append(limit)

        with sqlite3.connect(self.db_path) as con:
            rows = con.execute(sql, args).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(r) -> MemoryNote:
        return MemoryNote(
            id=r[0],
            created_at=datetime.fromisoformat(r[1]),
            agent=r[2],
            kind=MemoryKind(r[3]),
            symbol=r[4],
            content=r[5],
            confidence=r[6],
            importance=r[7],
            tags=json.loads(r[8]),
            sources=json.loads(r[9]),
            expires_at=datetime.fromisoformat(r[10]) if r[10] else None,
            supersedes_id=r[11],
            status=r[12],
            as_of_date=datetime.fromisoformat(r[13]) if len(r) > 13 and r[13] else None,
            point_in_time=datetime.fromisoformat(r[14]) if len(r) > 14 and r[14] else None,
            decision_id=r[15] if len(r) > 15 else None,
            claim_direction=ClaimDirection(r[16]) if len(r) > 16 and r[16] else None,
            entities=json.loads(r[17]) if len(r) > 17 and r[17] else {},
        )

    def summary(self, agent: str, symbol: Optional[str] = None, limit: int = 12) -> str:
        notes = self.list_notes(agent=agent, symbol=symbol, limit=limit, active_only=True)
        if not notes:
            return "No active prior memory."
        ordered = sorted(notes, key=lambda x: (x.importance, x.created_at), reverse=True)
        return "\n".join(
            f"[{n.created_at.date().isoformat()}][{n.kind.value}][conf={n.confidence:.2f}] {n.content}"
            for n in ordered[:limit]
        )

    def get_decayed_summary(
        self,
        agent: str,
        symbol: Optional[str] = None,
        as_of: Optional[datetime] = None,
        half_life_days: float = 30.0,
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves active notes with dynamically calculated time-decayed confidence.
        """
        notes = self.list_notes(agent=agent, symbol=symbol, limit=limit * 2, active_only=True)
        out = []
        for n in notes:
            decayed = calculate_decayed_confidence(n.confidence, n.created_at, as_of=as_of, half_life_days=half_life_days)
            out.append({
                "id": n.id,
                "created_at": n.created_at.isoformat(),
                "symbol": n.symbol,
                "kind": n.kind.value,
                "initial_confidence": n.confidence,
                "decayed_confidence": decayed,
                "content": n.content,
                "claim_direction": n.claim_direction.value if n.claim_direction else "NEUTRAL",
                "entities": n.entities,
            })
        out = sorted(out, key=lambda x: x["decayed_confidence"], reverse=True)
        return out[:limit]

    def agents(self) -> List[str]:
        with sqlite3.connect(self.db_path) as con:
            return [r[0] for r in con.execute("SELECT DISTINCT agent FROM agent_memory ORDER BY agent").fetchall()]

    def render_agent(self, agent: str) -> Path:
        notes = self.list_notes(agent=agent, limit=500, active_only=False)
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in agent)
        path = self.markdown_dir / f"{safe}.md"
        lines = [
            f"# Agent journal: {agent}",
            "",
            "> Generated from the SQLite audit ledger. Do not edit this file as agent memory; add/supersede ledger records instead.",
            "",
            f"Last rendered: {datetime.now(timezone.utc).isoformat()}",
            "",
        ]
        for n in sorted(notes, key=lambda x: (x.created_at, x.id or 0), reverse=True):
            state = n.status.upper()
            dir_str = f" | {n.claim_direction.value}" if n.claim_direction else ""
            lines += [
                f"## {n.created_at.isoformat()} | {n.kind.value}{dir_str} | {state}",
                "",
                f"- ID: `{n.id}`",
                f"- Symbol: `{n.symbol or 'GLOBAL'}`",
                f"- Confidence: `{n.confidence:.2f}`",
                f"- Importance: `{n.importance:.2f}`",
                f"- Decision ID: `{n.decision_id or 'none'}`",
                f"- Expires: `{n.expires_at.isoformat() if n.expires_at else 'never'}`",
                f"- Supersedes: `{n.supersedes_id or 'none'}`",
                f"- Tags: {', '.join(n.tags) if n.tags else 'none'}",
                f"- Sources: {', '.join(n.sources) if n.sources else 'none'}",
                f"- Entities: {json.dumps(n.entities) if n.entities else 'none'}",
                "",
                n.content,
                "",
            ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def render_all(self) -> List[Path]:
        return [self.render_agent(a) for a in self.agents()]
