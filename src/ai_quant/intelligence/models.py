from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class Direction(str, Enum):
    STRONG_BEARISH = "strong_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    STRONG_BULLISH = "strong_bullish"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class SourceTier(str, Enum):
    PRIMARY = "primary"
    TRUSTED_SECONDARY = "trusted_secondary"
    SECONDARY = "secondary"
    UNTRUSTED = "untrusted"
    SUSPICIOUS = "suspicious"


class EvidenceVerdict(str, Enum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    DISPUTED = "disputed"
    REJECTED = "rejected"


class EvidenceItem(BaseModel):
    claim: str = Field(min_length=3, max_length=4000)
    url: str = Field(min_length=8, max_length=4000)
    title: str = Field(default="", max_length=1000)
    source_domain: str = Field(default="", max_length=300)
    tier: SourceTier = SourceTier.SECONDARY
    published_at: Optional[str] = None
    suspicious_text: bool = False
    suspicious_reasons: List[str] = Field(default_factory=list)


class ClaimAssessment(BaseModel):
    claim: str
    verdict: EvidenceVerdict
    confidence: float = Field(ge=0.0, le=1.0)
    independent_sources: int = Field(ge=0)
    primary_sources: int = Field(ge=0)
    trusted_secondary_sources: int = Field(ge=0)
    sources: List[EvidenceItem] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class EvidenceReport(BaseModel):
    claims: List[ClaimAssessment] = Field(default_factory=list)
    overall_trust: float = Field(ge=0.0, le=1.0)
    verified_claim_ratio: float = Field(ge=0.0, le=1.0)
    disputed_claims: int = Field(ge=0)
    rejected_sources: int = Field(ge=0)
    source_domains: List[str] = Field(default_factory=list)


class ConflictPair(BaseModel):
    left_index: int = Field(ge=0)
    right_index: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=500)


class ConflictBatch(BaseModel):
    conflicts: List[ConflictPair] = Field(default_factory=list, max_length=30)


class TechnicalView(BaseModel):
    score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    direction: Direction
    trend: str
    momentum: str
    volatility: str
    mean_reversion_risk: str
    observations: List[str] = Field(default_factory=list)


class FundamentalSnapshot(BaseModel):
    symbol: str
    company_name: Optional[str] = None
    fiscal_year: Optional[int] = None
    revenue: Optional[float] = None
    revenue_growth: Optional[float] = None
    operating_income: Optional[float] = None
    operating_margin: Optional[float] = None
    net_income: Optional[float] = None
    net_margin: Optional[float] = None
    assets: Optional[float] = None
    asset_growth: Optional[float] = None
    liabilities: Optional[float] = None
    equity: Optional[float] = None
    debt: Optional[float] = None
    debt_to_equity: Optional[float] = None
    eps_diluted: Optional[float] = None
    source_url: Optional[str] = None


class FundamentalView(BaseModel):
    score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    direction: Direction
    quality: str
    growth: str
    balance_sheet: str
    profitability: str
    valuation_note: str
    observations: List[str] = Field(default_factory=list)
    snapshot: Optional[FundamentalSnapshot] = None


class TrendView(BaseModel):
    horizon: str
    score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    direction: Direction
    regime: str
    drivers: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class MacroSnapshot(BaseModel):
    fed_funds: Optional[float] = None
    unemployment: Optional[float] = None
    industrial_production_yoy: Optional[float] = None
    cpi_yoy: Optional[float] = None
    yield_curve_10y2y: Optional[float] = None
    as_of: Optional[str] = None


class FutureScenario(BaseModel):
    name: str
    horizon: str
    probability: float = Field(ge=0.0, le=1.0)
    direction: Direction
    thesis: str
    drivers: List[str] = Field(default_factory=list)
    invalidators: List[str] = Field(default_factory=list)


class FutureView(BaseModel):
    score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    scenarios: List[FutureScenario] = Field(min_length=2, max_length=5)
    unknowns: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_probabilities(self):
        total = sum(s.probability for s in self.scenarios)
        if not 0.85 <= total <= 1.15:
            raise ValueError("scenario probabilities should sum approximately to 1")
        return self


class HypothesisCheck(BaseModel):
    hypothesis: str
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_evidence: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    falsification_tests: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    survives: bool


class AISynthesis(BaseModel):
    future: FutureView
    hypothesis: HypothesisCheck
    key_risks: List[str] = Field(default_factory=list, max_length=12)


class ContextAdjustment(BaseModel):
    multiplier: float = Field(ge=0.0, le=1.05)
    context_score: float = Field(ge=-1.0, le=1.0)
    context_confidence: float = Field(ge=0.0, le=1.0)
    evidence_trust: float = Field(ge=0.0, le=1.0)
    block_new_buys: bool = False
    reasons: List[str] = Field(default_factory=list)


class ResearchDossier(BaseModel):
    symbol: str
    generated_at: datetime
    expires_at: datetime
    technical: TechnicalView
    fundamental: FundamentalView
    microtrend: TrendView
    megatrend: TrendView
    evidence: EvidenceReport
    future: FutureView
    hypothesis: HypothesisCheck
    adjustment: ContextAdjustment
    key_risks: List[str] = Field(default_factory=list)
