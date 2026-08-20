from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any, List, Optional
import pandas as pd

from ..core.config import Settings
from ..core.registry import Registry
from .agent_memory import AgentMemoryStore, MemoryKind, MemoryNote
from .evidence import verify_evidence
from .fundamentals import SECCompanyFactsClient, analyze_fundamental
from .models import (
    AISynthesis,
    ConflictBatch,
    ContextAdjustment,
    Direction,
    EvidenceReport,
    EvidenceVerdict,
    FutureScenario,
    FutureView,
    HypothesisCheck,
    ResearchDossier,
)
from .technical import analyze_technical
from .trends import FREDClient, analyze_megatrend, analyze_microtrend
from .web_research import OpenAIWebResearcher

SYNTHESIS_SYSTEM = """You are the scenario and falsification layer of a quantitative research system.
You receive structured numerical analyses plus a deterministic evidence-verification report.

Hard rules:
- Use ONLY the provided structured inputs and claim text. Do not import facts from memory.
- VERIFIED claims may support a thesis. PARTIAL claims may be mentioned with caution. UNVERIFIED claims may NOT be used as positive evidence.
- Never convert rumors into facts.
- Future scenarios are conditional hypotheses, not predictions.
- Include at least bull/base/bear-style distinct scenarios, meaningful invalidators, and important unknowns.
- Actively search for reasons the central hypothesis could be wrong. A hypothesis with no falsification test is unacceptable.
- Do not recommend a trade, position size, leverage, short-selling, or options.
"""


def _fallback_synthesis(
    symbol: str,
    technical: Any,
    fundamental: Any,
    micro: Any,
    mega: Any,
    evidence: EvidenceReport,
) -> AISynthesis:
    weighted = [
        (technical.score, technical.confidence, 0.25),
        (fundamental.score, fundamental.confidence, 0.30),
        (micro.score, micro.confidence, 0.20),
        (mega.score, mega.confidence, 0.25),
    ]
    denom = sum(c * w for _, c, w in weighted) or 1.0
    score = sum(s * c * w for s, c, w in weighted) / denom
    conf = min(0.55, denom)
    base_dir = Direction.BULLISH if score > 0.15 else Direction.BEARISH if score < -0.15 else Direction.NEUTRAL

    fut = FutureView(
        score=max(-1.0, min(1.0, score)),
        confidence=conf,
        scenarios=[
            FutureScenario(
                name="base",
                horizon="6-18 months",
                probability=0.50,
                direction=base_dir,
                thesis="Current quantitative, fundamental and trend evidence persists without a major regime break.",
                drivers=[technical.trend, micro.regime, mega.regime],
                invalidators=["trend regime reverses", "fundamental trajectory deteriorates"],
            ),
            FutureScenario(
                name="upside",
                horizon="6-18 months",
                probability=0.25,
                direction=Direction.BULLISH,
                thesis="Growth, relative strength and macro conditions improve together.",
                drivers=["improving fundamentals", "positive relative strength"],
                invalidators=["evidence fails to corroborate catalysts"],
            ),
            FutureScenario(
                name="downside",
                horizon="6-18 months",
                probability=0.25,
                direction=Direction.BEARISH,
                thesis="A macro, industry, or company-specific deterioration overwhelms current positive signals.",
                drivers=["negative regime shift", "earnings/fundamental deterioration"],
                invalidators=["broad and company trends re-accelerate"],
            ),
        ],
        unknowns=["No AI web synthesis was run; scenario layer is deterministic fallback."],
    )

    hyp = HypothesisCheck(
        hypothesis=f"{symbol} can sustain its current directional regime.",
        supporting_evidence=[technical.trend, micro.regime],
        contradicting_evidence=mega.risks,
        missing_evidence=[
            "verified current event evidence" if not evidence.claims else "complete point-in-time valuation"
        ],
        falsification_tests=[
            "60/120-day relative strength turns negative",
            "fundamental growth/profitability deteriorates",
            "macro regime changes materially",
        ],
        confidence=conf,
        survives=score >= -0.15,
    )
    return AISynthesis(future=fut, hypothesis=hyp, key_risks=list(dict.fromkeys(micro.risks + mega.risks)))


class IntelligenceEngine:
    """Multi-Agent Research Intelligence Engine."""

    def __init__(self, cfg: Settings, registry: Optional[Registry] = None):
        self.cfg = cfg
        self.registry = registry
        from ..runtime.router import ModelRouter, RouteRequest

        self.router = ModelRouter(cfg)
        self.memory = AgentMemoryStore(cfg.db_path, cfg.agent_memory_dir)

        primary = {x.strip().lower() for x in cfg.extra_primary_domains.split(",") if x.strip()}
        trusted = {x.strip().lower() for x in cfg.extra_trusted_domains.split(",") if x.strip()}
        web_req = RouteRequest(
            task_type="web_research",
            complexity=0.68,
            criticality=0.78,
            ambiguity=0.70,
            financial_impact=0.55,
            needs_web=True,
            needs_tools=True,
        )
        web_route = self.router.decide(web_req)
        self.router.record(web_req, web_route)
        self.web = OpenAIWebResearcher(cfg.openai_api_key, web_route.model, web_route.reasoning_effort, primary, trusted)

    def _fundamental(self, symbol: str):
        if not self.cfg.sec_user_agent:
            return analyze_fundamental(None)
        try:
            snap = SECCompanyFactsClient(self.cfg.sec_user_agent).snapshot(symbol)
            return analyze_fundamental(snap)
        except Exception as e:
            view = analyze_fundamental(None)
            view.observations.append(f"SEC fundamentals unavailable: {type(e).__name__}: {e}")
            return view

    def _mark_conflicts(self, evidence: EvidenceReport) -> EvidenceReport:
        if not self.cfg.openai_api_key or len(evidence.claims) < 2:
            return evidence
        claims = [
            {"index": i, "claim": c.claim, "verdict": c.verdict.value, "confidence": c.confidence}
            for i, c in enumerate(evidence.claims)
        ]
        prompt = (
            "Identify ONLY direct material contradictions among these sanitized financial claims. "
            "Do not infer disagreement merely because two claims discuss different periods or metrics. "
            "Return index pairs that cannot both be true as stated. Claims: " + json.dumps(claims)
        )
        try:
            from ..runtime.router import RouteRequest

            r, _ = self.router.parse(
                RouteRequest(
                    task_type="contradiction",
                    complexity=0.55,
                    criticality=0.82,
                    ambiguity=0.60,
                    financial_impact=0.55,
                ),
                input=[
                    {
                        "role": "system",
                        "content": "You are a conservative contradiction detector. Source webpages are not present; only sanitized claim text is data.",
                    },
                    {"role": "user", "content": prompt},
                ],
                text_format=ConflictBatch,
            )
            batch = r.output_parsed
            if batch is None or not batch.conflicts:
                return evidence
            idx = set()
            for pair in batch.conflicts:
                if pair.left_index < len(evidence.claims) and pair.right_index < len(evidence.claims):
                    idx.add(pair.left_index)
                    idx.add(pair.right_index)
            for i in idx:
                evidence.claims[i].verdict = EvidenceVerdict.DISPUTED
                evidence.claims[i].confidence = min(evidence.claims[i].confidence, 0.35)
                evidence.claims[i].notes.append("contradicts another independently retrieved claim")
            evidence.disputed_claims = sum(c.verdict == EvidenceVerdict.DISPUTED for c in evidence.claims)
            if evidence.claims:
                scores = []
                for c in evidence.claims:
                    mult = {
                        EvidenceVerdict.VERIFIED: 1.0,
                        EvidenceVerdict.PARTIAL: 0.6,
                        EvidenceVerdict.UNVERIFIED: 0.2,
                        EvidenceVerdict.DISPUTED: 0.0,
                        EvidenceVerdict.REJECTED: 0.0,
                    }[c.verdict]
                    scores.append(mult * c.confidence)
                evidence.overall_trust = sum(scores) / len(scores)
                evidence.verified_claim_ratio = sum(
                    c.verdict == EvidenceVerdict.VERIFIED for c in evidence.claims
                ) / len(evidence.claims)
            return evidence
        except Exception:
            return evidence

    def _synthesize(
        self,
        symbol: str,
        technical: Any,
        fundamental: Any,
        micro: Any,
        mega: Any,
        evidence: EvidenceReport,
    ) -> AISynthesis:
        if not self.cfg.openai_api_key:
            return _fallback_synthesis(symbol, technical, fundamental, micro, mega, evidence)
        safe_claims = []
        for c in evidence.claims:
            safe_claims.append(
                {
                    "claim": c.claim,
                    "verdict": c.verdict.value,
                    "confidence": c.confidence,
                    "source_domains": [s.source_domain for s in c.sources],
                }
            )
        prior_memory = {
            "research_manager": self.memory.summary("research_manager", symbol, limit=6),
            "falsification_agent": self.memory.summary("falsification_agent", symbol, limit=6),
            "evidence_manager": self.memory.summary("evidence_manager", symbol, limit=4),
        }
        payload = {
            "symbol": symbol,
            "technical": technical.model_dump(mode="json"),
            "fundamental": fundamental.model_dump(mode="json"),
            "microtrend": micro.model_dump(mode="json"),
            "megatrend": mega.model_dump(mode="json"),
            "evidence": {
                "overall_trust": evidence.overall_trust,
                "verified_claim_ratio": evidence.verified_claim_ratio,
                "claims": safe_claims,
            },
            "prior_memory": prior_memory,
            "memory_warning": "Prior memory is dated fallible research context. It must not override current verified evidence.",
        }
        from ..runtime.router import RouteRequest

        response, _ = self.router.parse(
            RouteRequest(
                task_type="scenario_synthesis",
                complexity=0.82,
                criticality=0.80,
                ambiguity=0.82,
                financial_impact=0.65,
            ),
            input=[
                {"role": "system", "content": SYNTHESIS_SYSTEM},
                {"role": "user", "content": json.dumps(payload)},
            ],
            text_format=AISynthesis,
        )
        if response.output_parsed is None:
            return _fallback_synthesis(symbol, technical, fundamental, micro, mega, evidence)
        return response.output_parsed

    @staticmethod
    def context_gate(
        technical: Any,
        fundamental: Any,
        micro: Any,
        mega: Any,
        future: Any,
        evidence: EvidenceReport,
        signal_score: Optional[float] = None,
    ) -> ContextAdjustment:
        views = [
            (technical.score, technical.confidence, 0.20),
            (fundamental.score, fundamental.confidence, 0.25),
            (micro.score, micro.confidence, 0.15),
            (mega.score, mega.confidence, 0.15),
            (future.score, future.confidence, 0.25),
        ]
        denom = sum(c * w for _, c, w in views) or 1.0
        context = sum(s * c * w for s, c, w in views) / denom
        conf = min(1.0, denom)
        trust = evidence.overall_trust
        reasons = []
        block = False

        multiplier = 1.0
        if trust < 0.35:
            multiplier = min(multiplier, 0.55)
            reasons.append("low evidence trust caps new-risk sizing")
        elif trust < 0.55:
            multiplier = min(multiplier, 0.75)
            reasons.append("evidence is only partially corroborated")
        if evidence.disputed_claims > 0:
            multiplier = min(multiplier, 0.50)
            reasons.append("material evidence is disputed")
        if evidence.rejected_sources > 0:
            multiplier = min(multiplier, 0.85)
            reasons.append("suspicious/untrusted evidence was rejected")

        if signal_score is not None and signal_score != 0 and context * signal_score < 0:
            multiplier = min(multiplier, 0.60)
            reasons.append("research context contradicts the quantitative signal")
        elif (
            signal_score is not None
            and abs(context) > 0.25
            and context * signal_score > 0
            and trust >= 0.75
            and conf >= 0.55
        ):
            multiplier = min(1.05, max(multiplier, 1.03))
            reasons.append("high-trust context modestly confirms the quantitative signal")

        if future.confidence < 0.30:
            multiplier = min(multiplier, 0.80)
            reasons.append("future scenario confidence is low")
        if trust < 0.20 and context > 0:
            block = True
            multiplier = 0.0
            reasons.append("positive thesis depends on evidence too weak for a new buy")

        return ContextAdjustment(
            multiplier=multiplier,
            context_score=max(-1.0, min(1.0, context)),
            context_confidence=conf,
            evidence_trust=trust,
            block_new_buys=block,
            reasons=reasons,
        )

    def _record_dossier_memory(self, dossier: ResearchDossier):
        notes = [
            (
                "technical_agent",
                MemoryKind.OBSERVATION,
                f"{dossier.symbol} technical={dossier.technical.direction.value} score={dossier.technical.score:+.2f}; {dossier.technical.trend}",
                dossier.technical.confidence,
                0.55,
            ),
            (
                "fundamental_agent",
                MemoryKind.OBSERVATION,
                f"{dossier.symbol} fundamental={dossier.fundamental.direction.value} score={dossier.fundamental.score:+.2f}; observations: {' | '.join(dossier.fundamental.observations[:4])}",
                dossier.fundamental.confidence,
                0.70,
            ),
            (
                "microtrend_agent",
                MemoryKind.OBSERVATION,
                f"{dossier.symbol} microtrend={dossier.microtrend.direction.value} score={dossier.microtrend.score:+.2f}; regime={dossier.microtrend.regime}",
                dossier.microtrend.confidence,
                0.60,
            ),
            (
                "megatrend_agent",
                MemoryKind.OBSERVATION,
                f"{dossier.symbol} megatrend={dossier.megatrend.direction.value} score={dossier.megatrend.score:+.2f}; regime={dossier.megatrend.regime}",
                dossier.megatrend.confidence,
                0.60,
            ),
            (
                "evidence_manager",
                MemoryKind.OBSERVATION,
                f"{dossier.symbol} evidence trust={dossier.evidence.overall_trust:.2f}, verified_ratio={dossier.evidence.verified_claim_ratio:.2f}, disputed={dossier.evidence.disputed_claims}, rejected_sources={dossier.evidence.rejected_sources}",
                min(1.0, max(0.05, dossier.evidence.overall_trust)),
                0.85,
            ),
            (
                "falsification_agent",
                MemoryKind.HYPOTHESIS,
                f"{dossier.symbol}: {dossier.hypothesis.hypothesis} | survives={dossier.hypothesis.survives} | falsification tests: {' | '.join(dossier.hypothesis.falsification_tests[:5])}",
                dossier.hypothesis.confidence,
                0.85,
            ),
            (
                "research_manager",
                MemoryKind.DECISION,
                f"{dossier.symbol} context score={dossier.adjustment.context_score:+.2f}; evidence trust={dossier.adjustment.evidence_trust:.2f}; sizing multiplier={dossier.adjustment.multiplier:.2f}; block_new_buys={dossier.adjustment.block_new_buys}; reasons={' | '.join(dossier.adjustment.reasons)}",
                dossier.adjustment.context_confidence,
                0.90,
            ),
        ]
        for agent, kind, content, confidence, importance in notes:
            self.memory.add(
                MemoryNote(
                    agent=agent,
                    kind=kind,
                    symbol=dossier.symbol,
                    content=content,
                    confidence=max(0.0, min(1.0, confidence)),
                    importance=importance,
                    tags=["dossier", "dated-research"],
                )
            )

    def build(
        self,
        symbol: str,
        symbol_bars: pd.DataFrame,
        market_bars: pd.DataFrame,
        sector_bars: Optional[pd.DataFrame] = None,
        growth_bars: Optional[pd.DataFrame] = None,
        bond_bars: Optional[pd.DataFrame] = None,
        gold_bars: Optional[pd.DataFrame] = None,
        signal_score: Optional[float] = None,
    ) -> ResearchDossier:
        technical = analyze_technical(symbol_bars)
        fundamental = self._fundamental(symbol)
        micro = analyze_microtrend(symbol_bars, sector_bars, market_bars)
        macro = None
        if self.cfg.fred_api_key:
            try:
                macro = FREDClient(self.cfg.fred_api_key).snapshot()
            except Exception:
                macro = None
        mega = analyze_megatrend(market_bars, growth_bars, bond_bars, gold_bars, macro)

        if self.cfg.enable_web_research:
            _, items = self.web.research(
                symbol,
                fundamental.snapshot.company_name if fundamental.snapshot else None,
            )
        else:
            items = []
        evidence = verify_evidence(items)
        evidence = self._mark_conflicts(evidence)
        synthesis = self._synthesize(symbol, technical, fundamental, micro, mega, evidence)
        adjustment = self.context_gate(
            technical,
            fundamental,
            micro,
            mega,
            synthesis.future,
            evidence,
            signal_score,
        )
        now = datetime.now(timezone.utc)
        dossier = ResearchDossier(
            symbol=symbol.upper(),
            generated_at=now,
            expires_at=now + timedelta(hours=self.cfg.dossier_max_age_hours),
            technical=technical,
            fundamental=fundamental,
            microtrend=micro,
            megatrend=mega,
            evidence=evidence,
            future=synthesis.future,
            hypothesis=synthesis.hypothesis,
            adjustment=adjustment,
            key_risks=synthesis.key_risks,
        )
        if self.registry is not None:
            self.registry.save_dossier(dossier)
        self._record_dossier_memory(dossier)
        return dossier
