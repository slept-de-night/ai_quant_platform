from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import json
import sqlite3
from typing import List, Optional
from pydantic import BaseModel, Field


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
    symbol: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    expires_at: Optional[datetime] = None
    supersedes_id: Optional[int] = None
    status: str = "active"


SCHEMA = """
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
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS idx_agent_memory_agent_time ON agent_memory(agent, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_memory_symbol_time ON agent_memory(symbol, created_at DESC);
"""


class AgentMemoryStore:
    """
    Append-first agent memory.
    SQLite is the source of truth. Markdown files are generated audit projections.
    """

    def __init__(self, db_path: str, markdown_dir: str = "agent_memory"):
        self.db_path = db_path
        self.markdown_dir = Path(markdown_dir)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as con:
            con.executescript(SCHEMA)

    def add(self, note: MemoryNote) -> MemoryNote:
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
                    tags_json, sources_json, expires_at, supersedes_id, status
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
            note.id = int(cur.lastrowid)
        self.render_agent(note.agent)
        return note

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

        sql = "SELECT id, created_at, agent, kind, symbol, content, confidence, importance, tags_json, sources_json, expires_at, supersedes_id, status FROM agent_memory"
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
            lines += [
                f"## {n.created_at.isoformat()} | {n.kind.value} | {state}",
                "",
                f"- ID: `{n.id}`",
                f"- Symbol: `{n.symbol or 'GLOBAL'}`",
                f"- Confidence: `{n.confidence:.2f}`",
                f"- Importance: `{n.importance:.2f}`",
                f"- Expires: `{n.expires_at.isoformat() if n.expires_at else 'never'}`",
                f"- Supersedes: `{n.supersedes_id or 'none'}`",
                f"- Tags: {', '.join(n.tags) if n.tags else 'none'}",
                f"- Sources: {', '.join(n.sources) if n.sources else 'none'}",
                "",
                n.content,
                "",
            ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def render_all(self) -> List[Path]:
        return [self.render_agent(a) for a in self.agents()]
