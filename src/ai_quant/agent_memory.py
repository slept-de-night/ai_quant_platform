"""Compatibility alias for intelligence.agent_memory"""
from .intelligence.agent_memory import *
from .intelligence.agent_memory import (
    MemoryKind,
    MemoryNote,
    AgentMemoryStore,
    ClaimDirection,
    Contradiction,
    extract_entities,
    classify_claim_direction,
    calculate_decayed_confidence,
    detect_contradictions,
)

__all__ = [
    "MemoryKind",
    "MemoryNote",
    "AgentMemoryStore",
    "ClaimDirection",
    "Contradiction",
    "extract_entities",
    "classify_claim_direction",
    "calculate_decayed_confidence",
    "detect_contradictions",
]
