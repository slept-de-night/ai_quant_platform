from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Union

from ..core.config import Settings
from ..core.models import CandidateBatch, ResearchCandidate
from ..data.features import FEATURE_COLUMNS
from ..quant.factors import seed_strategies, validate_spec
from .agent_memory import AgentMemoryStore, MemoryKind, MemoryNote

SYSTEM = """You are an alpha-research agent, not a trader.
Generate testable LONG/CASH daily-equity factor strategies using only the allowed feature names and transforms.
Do not generate code, orders, leverage, options, short-selling, unsupported news claims, or future data.
Prefer economically distinct hypotheses rather than cosmetic parameter changes.
Use prior memory as fallible historical evidence, not as truth. Explicitly avoid repeating known failure modes.
The output is only a research candidate and must be independently walk-forward tested."""


class AlphaResearchAgent:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        from ..runtime.router import ModelRouter

        self.router = ModelRouter(cfg)
        self.memory = AgentMemoryStore(cfg.db_path, cfg.agent_memory_dir)
        self.last_decision = None

    def generate(
        self,
        count: int = 6,
        experiment_summary: str = "",
        symbol: Optional[str] = None,
    ) -> List[ResearchCandidate]:
        count = max(1, min(12, count))
        if not self.cfg.openai_api_key:
            return self._fallback(count)

        memory = self.memory.summary("alpha_research_agent", symbol, limit=self.cfg.agent_memory_max_prompt_notes)
        prompt = (
            f"Allowed features: {sorted(FEATURE_COLUMNS)}\nAllowed transforms: identity,tanh,sign,negate\n"
            f"Generate {count} candidates.\nExperiment summary:\n{experiment_summary or 'none'}\n"
            f"Dated agent memory (may be stale or superseded; treat cautiously):\n{memory}"
        )

        from ..runtime.router import RouteRequest

        req = RouteRequest(
            task_type="alpha_generation",
            complexity=0.80,
            criticality=0.72,
            ambiguity=0.75,
            financial_impact=0.45,
            quality_first=False,
        )
        response, decision = self.router.parse(
            req,
            input=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            text_format=CandidateBatch,
        )
        self.last_decision = decision
        batch = response.output_parsed
        if batch is None:
            raise RuntimeError("OpenAI returned no parsed candidate batch")

        out: List[ResearchCandidate] = []
        for c in batch.candidates[:count]:
            validate_spec(c.strategy)
            out.append(c)

        self.memory.add(
            MemoryNote(
                agent="alpha_research_agent",
                kind=MemoryKind.OBSERVATION,
                symbol=symbol,
                content=f"Generated {len(out)} candidate strategies using {decision.model}/{decision.reasoning_effort}. Candidates still require independent validation.",
                confidence=0.95,
                importance=0.45,
                tags=["generation", "model-route"],
                expires_at=datetime.now(timezone.utc)
                + timedelta(days=self.cfg.agent_memory_default_expiry_days),
            )
        )
        return out

    def record_result(
        self,
        symbol: str,
        candidate: ResearchCandidate,
        report_or_error: Union[Any, Exception],
    ):
        if isinstance(report_or_error, Exception):
            self.memory.add(
                MemoryNote(
                    agent="alpha_research_agent",
                    kind=MemoryKind.FAILURE,
                    symbol=symbol,
                    content=f"Candidate {candidate.strategy.name} failed to evaluate: {type(report_or_error).__name__}: {report_or_error}",
                    confidence=0.98,
                    importance=0.75,
                    tags=["validation", "failure"],
                )
            )
            return

        r = report_or_error
        kind = MemoryKind.LESSON if not r.passed else MemoryKind.OBSERVATION
        self.memory.add(
            MemoryNote(
                agent="alpha_research_agent",
                kind=kind,
                symbol=symbol,
                content=(
                    f"Candidate {candidate.strategy.name}: {'PASSED' if r.passed else 'FAILED'} walk-forward validation; "
                    f"robust={r.robust_score:.3f}, median_sharpe={r.median_sharpe:.3f}, worst_drawdown={r.worst_drawdown:.2%}. "
                    f"Hypothesis: {candidate.strategy.hypothesis}"
                ),
                confidence=0.98,
                importance=0.85 if r.passed else 0.65,
                tags=["walk-forward", "strategy-result"],
            )
        )

    def _fallback(self, count: int) -> List[ResearchCandidate]:
        rng = random.Random(42)
        seeds = seed_strategies()
        out = []
        while len(out) < count:
            base = seeds[len(out) % len(seeds)].model_copy(deep=True)
            base.name = f"{base.name}_mut_{len(out)+1}"
            base.hypothesis += (
                " This candidate perturbs weights and thresholds to test local robustness rather than asserting a new discovery."
            )
            for t in base.terms:
                t.weight = max(-2.0, min(2.0, t.weight * rng.uniform(0.75, 1.25)))
                t.scale = max(0.1, min(50.0, t.scale * rng.uniform(0.85, 1.15)))
            base.entry_threshold = max(0.05, min(0.80, base.entry_threshold + rng.uniform(-0.05, 0.07)))
            base.exit_threshold = min(
                base.entry_threshold - 0.01,
                max(-0.30, base.exit_threshold + rng.uniform(-0.04, 0.04)),
            )
            out.append(
                ResearchCandidate(
                    strategy=base,
                    why_different="Deterministic fallback mutation used because no OpenAI key is configured.",
                    failure_modes=[
                        "May be a cosmetic mutation rather than independent alpha",
                        "Synthetic-data success may not transfer to real markets",
                    ],
                )
            )
        return out
