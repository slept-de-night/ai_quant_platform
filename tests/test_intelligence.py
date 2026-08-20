from ai_quant.intelligence import IntelligenceEngine
from ai_quant.intelligence_models import (
    Direction, EvidenceReport, FundamentalView, FutureScenario, FutureView,
    TechnicalView, TrendView
)


def test_low_trust_reduces_context_sizing():
    tech=TechnicalView(score=.5,confidence=.8,direction=Direction.BULLISH,trend="up",momentum="up",volatility="moderate",mean_reversion_risk="none")
    fund=FundamentalView(score=.4,confidence=.7,direction=Direction.BULLISH,quality="strong",growth="positive",balance_sheet="moderate",profitability="positive",valuation_note="n/a")
    micro=TrendView(horizon="weeks",score=.4,confidence=.7,direction=Direction.BULLISH,regime="leadership")
    mega=TrendView(horizon="years",score=.3,confidence=.7,direction=Direction.BULLISH,regime="risk-on")
    future=FutureView(score=.4,confidence=.6,scenarios=[
        FutureScenario(name="base",horizon="1y",probability=.5,direction=Direction.BULLISH,thesis="x"),
        FutureScenario(name="bear",horizon="1y",probability=.25,direction=Direction.BEARISH,thesis="y"),
        FutureScenario(name="bull",horizon="1y",probability=.25,direction=Direction.STRONG_BULLISH,thesis="z"),
    ])
    evidence=EvidenceReport(claims=[],overall_trust=.2,verified_claim_ratio=0,disputed_claims=0,rejected_sources=0,source_domains=[])
    adj=IntelligenceEngine.context_gate(tech,fund,micro,mega,future,evidence,signal_score=.5)
    assert adj.multiplier <= .55
