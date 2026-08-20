from __future__ import annotations

import pandas as pd

from ..core.config import Settings
from ..core.models import PortfolioState, RiskDecision, Side, Signal
from ..core.registry import Registry
from ..data.features import feature_frame
from ..data.regime import latest_regime
from ..intelligence.engine import IntelligenceEngine
from ..quant.factors import compile_score
from .risk import RiskEngine


class PaperTradingEngine:
    """Quantitative signal generation, research gating, and risk evaluation engine."""

    def __init__(self, cfg: Settings, registry: Registry):
        self.cfg = cfg
        self.registry = registry
        self.risk = RiskEngine(cfg)

    def signal(self, symbol: str, bars: pd.DataFrame, strategy_name: str) -> Signal:
        spec, _ = self.registry.get(strategy_name, require_approved=True)
        f = feature_frame(bars).dropna()
        score = float(compile_score(f, spec).iloc[-1])
        regime = latest_regime(f)
        price = float(f["close"].iloc[-1])

        allowed = {r.value for r in spec.regime_allow}
        regime_ok = not allowed or regime.value in allowed
        if not regime_ok:
            side = Side.SELL
        elif score >= spec.entry_threshold:
            side = Side.BUY
        elif score <= spec.exit_threshold:
            side = Side.SELL
        else:
            side = Side.HOLD

        reason = (
            f"score={score:.3f}, entry={spec.entry_threshold:.3f}, exit={spec.exit_threshold:.3f}, regime={regime.value}"
        )
        multiplier = 1.0
        trust = 1.0

        dossier = self.registry.get_dossier(symbol, require_fresh=True)
        if dossier is not None:
            adj = IntelligenceEngine.context_gate(
                dossier.technical,
                dossier.fundamental,
                dossier.microtrend,
                dossier.megatrend,
                dossier.future,
                dossier.evidence,
                score,
            )
            multiplier = adj.multiplier
            trust = adj.evidence_trust
            if side == Side.BUY and adj.block_new_buys:
                side = Side.HOLD
                reason += "; research gate blocked new buy"
            if adj.reasons:
                reason += "; context=" + " | ".join(adj.reasons)
        elif self.cfg.require_fresh_dossier and side == Side.BUY:
            side = Side.HOLD
            multiplier = 0.0
            trust = 0.0
            reason += "; fresh research dossier required before a new buy"

        return Signal(
            symbol=symbol,
            strategy_name=spec.name,
            score=score,
            side=side,
            reference_price=price,
            regime=regime,
            reason=reason,
            context_multiplier=multiplier,
            context_trust=trust,
        )

    def decide(self, signal: Signal, portfolio: PortfolioState) -> RiskDecision:
        return self.risk.evaluate(signal, portfolio)
