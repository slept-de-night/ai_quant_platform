from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from typing import Dict, List, Optional

from .pit import PITObservation, PITStore


@dataclass(frozen=True)
class QuantSnapshot:
    """Immutable point-in-time market and feature snapshot with cryptographic provenance.
    
    Attributes:
        decision_time: Exact timestamp of the decision.
        observations: Immutable list of observations known at or before decision_time.
        snapshot_id: Deterministic SHA256 hash of decision_time and observation content hashes.
    """
    decision_time: datetime
    observations: List[PITObservation]
    snapshot_id: str

    @classmethod
    def create(
        cls,
        decision_time: datetime,
        observations: List[PITObservation],
    ) -> QuantSnapshot:
        # Sort observations by observation_id to ensure deterministic hashing
        sorted_obs = sorted(observations, key=lambda x: (x.symbol, x.feature_name, x.effective_at, x.observation_id))
        
        hasher = hashlib.sha256()
        hasher.update(decision_time.isoformat().encode("utf-8"))
        for obs in sorted_obs:
            hasher.update(obs.content_hash.encode("utf-8"))
        snapshot_id = hasher.hexdigest()

        return cls(
            decision_time=decision_time,
            observations=sorted_obs,
            snapshot_id=snapshot_id,
        )

    def get_feature(self, symbol: str, feature_name: str) -> Optional[Any]:
        """Query the latest known value of a feature within this snapshot."""
        symbol = symbol.upper().strip()
        matches = [
            obs for obs in self.observations
            if obs.symbol == symbol and obs.feature_name == feature_name
        ]
        if not matches:
            return None
        # Sort by effective_at ascending, take latest
        matches.sort(key=lambda x: x.effective_at)
        return matches[-1].value

    def get_series(self, symbol: str, feature_name: str) -> List[tuple[datetime, Any]]:
        """Query historical time-series of a feature within this snapshot."""
        symbol = symbol.upper().strip()
        matches = [
            obs for obs in self.observations
            if obs.symbol == symbol and obs.feature_name == feature_name
        ]
        matches.sort(key=lambda x: x.effective_at)
        return [(m.effective_at, m.value) for m in matches]


class SnapshotResolver:
    """Resolves point-in-time QuantSnapshot from a PITStore."""

    def __init__(self, pit_store: PITStore):
        self.store = pit_store

    def build_snapshot(
        self,
        symbols: List[str],
        decision_time: datetime,
    ) -> QuantSnapshot:
        all_obs: List[PITObservation] = []
        for sym in symbols:
            obs = self.store.get_known_at(sym, as_of_time=decision_time)
            all_obs.extend(obs)
        return QuantSnapshot.create(decision_time=decision_time, observations=all_obs)
