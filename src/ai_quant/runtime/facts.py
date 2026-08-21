from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ResearchFact(BaseModel):
    """Atomic, point-in-time verified fact extracted from market, fundamental, or macro data.

    Facts are distinct from interpretations: facts represent measured, objective
    observations with cryptographic provenance, strict timestamp bounds, and source traceability.
    """

    fact_id: str
    symbol: Optional[str] = None
    category: str  # 'market', 'technical', 'fundamental', 'macro', 'evidence', 'portfolio_context'
    key: str
    value: Any

    observed_at: datetime
    known_at: datetime
    as_of: datetime

    source_type: str  # e.g. 'market_data', 'sec_edgar', 'fred', 'derived_technical', 'evidence_ledger'
    source_id: Optional[str] = None
    source_hash: Optional[str] = None

    dataset_version: Optional[str] = "v1.0"
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def semantic_hash(self) -> str:
        """Deterministic fingerprint of the economic fact content alone (independent of run/as_of)."""
        val_str = (
            json.dumps(self.value, sort_keys=True, default=str)
            if isinstance(self.value, (dict, list))
            else str(self.value)
        )
        s = (
            f"{self.symbol or ''}:{self.category}:{self.key}:{val_str}:"
            f"{self.observed_at.isoformat()}:{self.known_at.isoformat()}:"
            f"{self.source_type}:{self.dataset_version or ''}:{self.confidence}"
        )
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    @property
    def provenance_hash(self) -> str:
        """Full cryptographic provenance hash tying fact identity, decision as_of, and sources."""
        s = f"{self.fact_id}:{self.semantic_hash}:{self.as_of.isoformat()}:{self.source_id or ''}:{self.source_hash or ''}"
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    @property
    def content_hash(self) -> str:
        """Backward-compatible content hash property (returns semantic_hash)."""
        return self.semantic_hash
