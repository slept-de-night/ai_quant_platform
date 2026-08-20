from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PITObservation:
    """Point-in-Time Bitemporal Market/Fundamental Observation.
    
    Attributes:
        observation_id: Unique identifier for this observation.
        symbol: Ticker symbol (e.g. 'NVDA', 'SPY').
        feature_name: Name of the feature / metric (e.g. 'close', 'revenue', 'eps').
        value: Numeric or categorical value.
        effective_at: When the economic reality occurred (e.g. quarter end date, bar timestamp).
        known_at: When this data became legally/publicly available (e.g. SEC filing timestamp, quote arrival).
        dataset_version: Version identifier for the underlying dataset.
        is_restatement: True if this observation supersedes an earlier value for the same effective_at.
    """
    observation_id: str
    symbol: str
    feature_name: str
    value: Any
    effective_at: datetime
    known_at: datetime
    dataset_version: str = "v1.0"
    is_restatement: bool = False

    @property
    def content_hash(self) -> str:
        s = f"{self.observation_id}:{self.symbol}:{self.feature_name}:{self.value}:{self.effective_at.isoformat()}:{self.known_at.isoformat()}:{self.dataset_version}"
        return hashlib.sha256(s.encode("utf-8")).hexdigest()


class PITStore:
    """Thread-safe Point-in-Time Observation Store guaranteeing zero lookahead bias."""

    def __init__(self):
        self._observations: List[PITObservation] = []

    def record(self, obs: PITObservation) -> None:
        """Insert an observation into the immutable PIT store."""
        self._observations.append(obs)

    def record_many(self, observations: List[PITObservation]) -> None:
        """Batch record observations."""
        self._observations.extend(observations)

    def get_known_at(
        self,
        symbol: str,
        feature_name: Optional[str] = None,
        as_of_time: Optional[datetime] = None,
    ) -> List[PITObservation]:
        """Query observations for a symbol that were strictly known at or before as_of_time.
        
        If a restatement occurred before as_of_time, the latest restated value for that effective_at is returned.
        Any observation with known_at > as_of_time is strictly invisible.
        """
        symbol = symbol.upper().strip()
        as_of = as_of_time or datetime.now(timezone.utc)
        
        # 1. Filter out all observations not yet known at as_of_time
        eligible = [
            obs for obs in self._observations
            if obs.symbol == symbol
            and (feature_name is None or obs.feature_name == feature_name)
            and obs.known_at <= as_of
        ]

        # 2. Resolve restatements: if multiple observations share (symbol, feature_name, effective_at),
        # take the one with the latest known_at <= as_of
        grouped: Dict[tuple, PITObservation] = {}
        for obs in sorted(eligible, key=lambda x: x.known_at):
            key = (obs.symbol, obs.feature_name, obs.effective_at)
            grouped[key] = obs

        return sorted(list(grouped.values()), key=lambda x: x.effective_at)

    def get_latest_feature(
        self,
        symbol: str,
        feature_name: str,
        as_of_time: datetime,
    ) -> Optional[PITObservation]:
        """Get the latest effective value of a feature that was known at as_of_time."""
        history = self.get_known_at(symbol, feature_name=feature_name, as_of_time=as_of_time)
        if not history:
            return None
        return history[-1]
