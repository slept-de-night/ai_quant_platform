from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from typing import Optional
from pydantic import BaseModel, Field

from ..core.config import Settings
from .agent_memory import AgentMemoryStore, MemoryKind, MemoryNote


class MemoryMaintenance:
    """Non-destructive memory housekeeping and checkpoint consolidation."""

    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.store = AgentMemoryStore(cfg.db_path, cfg.agent_memory_dir)
        from ..runtime.router import ModelRouter

        self.router = ModelRouter(cfg)

    def expire_due(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.cfg.db_path) as con:
            rows = con.execute(
                "SELECT id, agent FROM agent_memory WHERE status='active' AND expires_at IS NOT NULL AND expires_at<=?",
                (now,),
            ).fetchall()
            con.execute(
                "UPDATE agent_memory SET status='expired' WHERE status='active' AND expires_at IS NOT NULL AND expires_at<=?",
                (now,),
            )
        for agent in sorted({r[1] for r in rows}):
            self.store.render_agent(agent)
        return len(rows)

    def checkpoint(self, agent: str, symbol: Optional[str] = None, limit: int = 20) -> Optional[MemoryNote]:
        notes = self.store.list_notes(agent=agent, symbol=symbol, limit=limit, active_only=True)
        notes = [n for n in notes if "checkpoint" not in n.tags]
        if len(notes) < 2:
            return None
        ordered = sorted(notes, key=lambda n: n.created_at)
        refs = [f"memory:{n.id}" for n in ordered if n.id is not None]
        payload = [
            {
                "id": n.id,
                "date": n.created_at.date().isoformat(),
                "kind": n.kind.value,
                "confidence": n.confidence,
                "importance": n.importance,
                "content": n.content,
            }
            for n in ordered
        ]

        if self.cfg.openai_api_key:

            class Summary(BaseModel):
                durable_lessons: list[str] = Field(default_factory=list, max_length=8)
                unresolved_questions: list[str] = Field(default_factory=list, max_length=6)
                stale_or_conflicting_items: list[str] = Field(default_factory=list, max_length=6)

            from ..runtime.router import RouteRequest

            response, _ = self.router.parse(
                RouteRequest(
                    task_type="summarize_notes",
                    complexity=0.35,
                    criticality=0.45,
                    ambiguity=0.35,
                    financial_impact=0.10,
                ),
                input=[
                    {
                        "role": "system",
                        "content": "Summarize agent memory conservatively. Preserve uncertainty and dates. Do not turn hypotheses into facts. Do not erase source notes.",
                    },
                    {"role": "user", "content": json.dumps(payload)},
                ],
                text_format=Summary,
            )
            sm = response.output_parsed
            content = (
                "Memory checkpoint derived from notes "
                + ", ".join(str(n.id) for n in ordered)
                + ".\n"
                + "Durable lessons: "
                + (" | ".join(sm.durable_lessons) if sm else "none")
                + "\n"
                + "Unresolved: "
                + (" | ".join(sm.unresolved_questions) if sm else "none")
                + "\n"
                + "Conflicts/stale: "
                + (" | ".join(sm.stale_or_conflicting_items) if sm else "none")
            )
        else:
            top = sorted(ordered, key=lambda n: (n.importance, n.confidence), reverse=True)[:6]
            content = (
                "Deterministic memory checkpoint. Original notes remain authoritative audit records. "
                + " | ".join(f"#{n.id} {n.kind.value}: {n.content[:220]}" for n in top)
            )

        return self.store.add(
            MemoryNote(
                agent=agent,
                kind=MemoryKind.LESSON,
                content=content,
                symbol=symbol,
                confidence=min(0.80, sum(n.confidence for n in ordered) / len(ordered)),
                importance=max(0.55, sum(n.importance for n in ordered) / len(ordered)),
                tags=["checkpoint", "derived-memory", f"source-count:{len(ordered)}"],
                sources=refs,
            )
        )
