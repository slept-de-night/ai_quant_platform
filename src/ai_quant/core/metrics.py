from __future__ import annotations

import time
import threading
from typing import Dict, Any


class PlatformMetrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.time()
        self.research_runs_total = 0
        self.model_router_latency_ms_total = 0.0
        self.model_router_calls = 0
        self.memory_notes_total = 0
        self.memory_contradictions_total = 0
        self.backtest_runs_total = 0

    def inc_research_runs(self, count: int = 1) -> None:
        with self._lock:
            self.research_runs_total += count

    def record_router_latency(self, latency_ms: float) -> None:
        with self._lock:
            self.model_router_latency_ms_total += latency_ms
            self.model_router_calls += 1

    def inc_memory_notes(self, count: int = 1) -> None:
        with self._lock:
            self.memory_notes_total += count

    def inc_memory_contradictions(self, count: int = 1) -> None:
        with self._lock:
            self.memory_contradictions_total += count

    def inc_backtest_runs(self, count: int = 1) -> None:
        with self._lock:
            self.backtest_runs_total += count

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            uptime = time.time() - self._start_time
            avg_latency = (
                self.model_router_latency_ms_total / self.model_router_calls
                if self.model_router_calls > 0
                else 0.0
            )
            return {
                "uptime_seconds": round(uptime, 2),
                "research_runs_total": self.research_runs_total,
                "model_router_calls": self.model_router_calls,
                "model_router_avg_latency_ms": round(avg_latency, 2),
                "memory_notes_total": self.memory_notes_total,
                "memory_contradictions_total": self.memory_contradictions_total,
                "backtest_runs_total": self.backtest_runs_total,
            }


# Singleton platform metrics instance
metrics = PlatformMetrics()
