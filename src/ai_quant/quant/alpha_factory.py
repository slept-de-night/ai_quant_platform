from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple, Union
import pandas as pd

from ..core.config import Settings
from ..core.models import ResearchCandidate, StrategySpec, StrategyStatus, ValidationReport
from ..core.registry import Registry
from .validation import walk_forward_validate

logger = logging.getLogger(__name__)


class AlphaFactory:
    """Orchestrates automated quantitative alpha generation, walk-forward validation, and cataloging."""

    def __init__(self, cfg: Settings, registry: Registry) -> None:
        self.cfg = cfg
        self.registry = registry

        # Lazy import of research agent to break circular import
        from ..intelligence.research import AlphaResearchAgent
        from ..runtime.evaluation import EvaluationManager

        self.agent = AlphaResearchAgent(cfg)
        self.evals = EvaluationManager(cfg)

    def run(
        self,
        symbol: str,
        bars: pd.DataFrame,
        count: Optional[int] = None,
    ) -> List[Tuple[ResearchCandidate, Union[ValidationReport, Exception]]]:
        """Generate candidate strategies, validate out-of-sample, and catalog successes."""
        candidate_count = count or self.cfg.alpha_candidates
        memory_summary = self.registry.memory_summary()
        candidates = self.agent.generate(candidate_count, memory_summary, symbol=symbol)

        results: List[Tuple[ResearchCandidate, Union[ValidationReport, Exception]]] = []

        for candidate in candidates:
            spec = candidate.strategy
            try:
                report = walk_forward_validate(
                    bars=bars,
                    spec=spec,
                    train_days=self.cfg.wf_train_days,
                    test_days=self.cfg.wf_test_days,
                    step_days=self.cfg.wf_step_days,
                    min_folds=self.cfg.min_wf_folds,
                    slippage_bps=self.cfg.slippage_bps,
                    commission_bps=self.cfg.commission_bps,
                    min_sharpe=self.cfg.min_validation_sharpe,
                    max_drawdown=self.cfg.max_validation_drawdown,
                    min_robust_score=self.cfg.min_robust_score,
                )
                status = StrategyStatus.VALIDATED if report.passed else StrategyStatus.CANDIDATE
                self.registry.upsert_strategy(spec, status=status, report=report)
                self.registry.record_experiment(symbol, spec, report)
                results.append((candidate, report))
            except Exception as e:
                logger.warning(f"Validation failed for candidate {spec.name}: {e}")
                results.append((candidate, e))

        return results
