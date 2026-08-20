from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional


class QuantClock(ABC):
    """Abstract time provider isolating alpha strategies from wall-clock dependencies."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current simulation or live time."""
        pass


class HistoricalClock(QuantClock):
    """Discrete steppable clock used for historical backtesting, CPCV, and deterministic replay."""

    def __init__(self, start_time: datetime):
        self._current_time = start_time

    def now(self) -> datetime:
        return self._current_time

    def set_time(self, new_time: datetime) -> None:
        self._current_time = new_time

    def advance(self, delta) -> datetime:
        self._current_time += delta
        return self._current_time


class LiveClock(QuantClock):
    """Real-time clock used for paper trading and live execution."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
