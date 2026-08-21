from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class RuntimeStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY = "retry"
    SUCCEEDED = "succeeded"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    REJECTED = "rejected"


class DelegationRequest(BaseModel):
    agent_role: str
    task_type: str
    objective: str
    complexity: float = Field(default=0.5, ge=0, le=1)
    criticality: float = Field(default=0.5, ge=0, le=1)
    ambiguity: float = Field(default=0.3, ge=0, le=1)
    financial_impact: float = Field(default=0, ge=0, le=1)
    estimated_tokens: int = Field(default=5000, ge=100, le=200000)
    needs_web: bool = False
    needs_tools: bool = False
    quality_first: bool = False


class TaskNode(BaseModel):
    task_id: str
    root_id: str
    parent_id: Optional[str] = None
    depth: int = 0
    agent_role: str
    task_type: str
    objective: str
    symbol: Optional[str] = None
    estimated_tokens: int = 5000
    status: TaskStatus = TaskStatus.PLANNED
    route: Optional[Any] = None
    execution_decision: Optional[Any] = None
    depends_on: List[str] = Field(default_factory=list)


class RuntimeTask(BaseModel):
    task_id: str
    root_id: str
    parent_id: Optional[str] = None
    agent_role: str
    task_type: str
    objective: str
    symbol: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 100
    attempts: int = 0
    max_attempts: int = 3
    status: RuntimeStatus = RuntimeStatus.QUEUED
    available_at: datetime
    lease_owner: Optional[str] = None
    lease_until: Optional[datetime] = None
    idempotency_key: str
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class RuntimeLogRecord(BaseModel):
    id: Optional[int] = None
    task_id: str
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    level: str
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


ALLOWED_AGENT_ROLES: Set[str] = {
    "research_manager",
    "market_structure_manager",
    "evidence_manager",
    "thesis_manager",
    "audit_agent",
    "technical_agent",
    "fundamental_agent",
    "microtrend_agent",
    "megatrend_agent",
    "web_research_agent",
    "contradiction_agent",
    "future_agent",
    "falsification_agent",
    "alpha_research_agent",
    "validation_agent",
}

ALLOWED_TASK_TYPES: Set[str] = {
    "research_program",
    "research_digest",
    "extract",
    "fundamental_review",
    "trend_review",
    "web_research",
    "contradiction",
    "scenario_synthesis",
    "falsification",
    "alpha_generation",
    "critical_review",
    "promotion_review",
    "summarize_notes",
    "journal",
    "deduplicate",
    "source_tier",
    "task_decomposition",
}
