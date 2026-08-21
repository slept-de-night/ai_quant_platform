"""
Agent Memory Intelligence Graph:
- Entity extraction (symbols, sectors, macro factors)
- Temporal anchoring (as_of_date, point_in_time)
- Causal claims / hypothesis tracking
- Conviction tracking & confidence decay
- Contradictory evidence detection
- Deduplication and conflict resolution
- Audit trails per decision_id
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class ClaimDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    RISK_ALERT = "RISK_ALERT"


class Contradiction(BaseModel):
    note_id: Optional[int] = None
    conflicting_note_id: int
    symbol: Optional[str] = None
    reason: str
    confidence_difference: float
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Curated Knowledge Base for Deterministic Entity Extraction
KNOWN_SECTORS: Dict[str, List[str]] = {
    "technology": ["tech", "software", "semiconductor", "semis", "hardware", "cloud", "saas", "cybersecurity", "ai"],
    "financials": ["bank", "banking", "insurance", "brokerage", "lending", "credit", "fintech"],
    "healthcare": ["pharma", "biotech", "medical", "therapeutics", "oncology", "clinical"],
    "energy": ["oil", "gas", "petroleum", "renewable", "solar", "drilling", "crude"],
    "consumer": ["retail", "ecommerce", "automotive", "luxury", "apparel", "food"],
    "industrials": ["defense", "aerospace", "machinery", "logistics", "shipping", "transport"],
    "materials": ["metals", "mining", "chemicals", "gold", "silver", "copper", "lithium"],
    "crypto": ["bitcoin", "ethereum", "blockchain", "defi", "solana", "altcoin"],
}

KNOWN_MACRO: List[str] = [
    "inflation", "cpi", "ppi", "interest rate", "fed", "fomc", "yield curve", "treasury",
    "gdp", "recession", "unemployment", "payroll", "dollar index", "dxy", "real yield",
    "quantitative tightening", "qt", "quantitative easing", "qe", "stagflation", "geopolitical",
]


def extract_entities(content: str, default_symbol: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Extracts structured entities from text: symbols, sectors, and macro factors.
    """
    lower = content.lower()

    # 1. Symbols: match $TICKER or explicit uppercase 2-5 letter tickers
    symbols: Set[str] = set()
    if default_symbol:
        symbols.add(default_symbol.upper())

    # Match $SYMBOL
    dollar_symbols = re.findall(r"\$([A-Za-z]{1,6}(?:=[A-Za-z0-9]+)?)", content)
    for s in dollar_symbols:
        symbols.add(s.upper())

    # Match standalone uppercase tickers
    word_tokens = re.findall(r"\b[A-Z]{2,5}\b", content)
    stopwords = {"THE", "AND", "FOR", "NEW", "NOT", "BUT", "ARE", "HAS", "HAD", "ALL", "ANY", "NOW", "ONE", "TWO", "SEE", "TOP", "LOW", "HIGH", "LONG", "SELL", "BUY", "HOLD", "OUT", "PER", "SET"}
    for tok in word_tokens:
        if tok not in stopwords:
            symbols.add(tok)

    # 2. Sectors
    sectors: Set[str] = set()
    for sector_name, keywords in KNOWN_SECTORS.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", lower):
                sectors.add(sector_name)
                break

    # 3. Macro factors
    macro_factors: Set[str] = set()
    for macro in KNOWN_MACRO:
        if re.search(r"\b" + re.escape(macro) + r"\b", lower):
            macro_factors.add(macro)

    return {
        "symbols": sorted(list(symbols)),
        "sectors": sorted(list(sectors)),
        "macro_factors": sorted(list(macro_factors)),
    }


def classify_claim_direction(content: str) -> ClaimDirection:
    """Classifies the sentiment / claim direction of a research note."""
    lower = content.lower()
    bullish_keywords = ["bullish", "long", "outperform", "undervalued", "accelerat", "expansion", "growth", "breakout", "accumulate", "buy"]
    bearish_keywords = ["bearish", "short", "underperform", "overvalued", "decelerat", "contraction", "headwind", "breakdown", "downgrade", "sell"]
    risk_keywords = ["risk", "warning", "fraud", "deteriorat", "default", "manipulation", "restatement", "violation"]

    risk_score = sum(1 for kw in risk_keywords if kw in lower)
    bull_score = sum(1 for kw in bullish_keywords if kw in lower)
    bear_score = sum(1 for kw in bearish_keywords if kw in lower)

    if risk_score >= 2 and risk_score > bull_score:
        return ClaimDirection.RISK_ALERT
    if bull_score > bear_score:
        return ClaimDirection.BULLISH
    if bear_score > bull_score:
        return ClaimDirection.BEARISH
    return ClaimDirection.NEUTRAL


def calculate_decayed_confidence(
    initial_confidence: float,
    created_at: datetime,
    as_of: Optional[datetime] = None,
    half_life_days: float = 30.0,
) -> float:
    """
    Computes time-decayed conviction / confidence:
    decayed_confidence = initial_confidence * (0.5 ** (delta_days / half_life_days))
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    delta_seconds = max(0.0, (as_of - created_at).total_seconds())
    delta_days = delta_seconds / 86400.0

    decay = math.pow(0.5, delta_days / max(1.0, half_life_days))
    return round(max(0.01, min(1.0, initial_confidence * decay)), 4)


def compute_text_similarity(a: str, b: str) -> float:
    """Computes Jaccard word-level similarity between two content strings for deduplication."""
    tokens_a = set(re.findall(r"\b[a-z0-9]+\b", a.lower()))
    tokens_b = set(re.findall(r"\b[a-z0-9]+\b", b.lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a.intersection(tokens_b))
    union = len(tokens_a.union(tokens_b))
    return intersection / union if union > 0 else 0.0


def detect_contradictions(
    new_content: str,
    new_symbol: Optional[str],
    new_confidence: float,
    existing_notes: List[Any],
) -> List[Contradiction]:
    """
    Detects contradictory evidence between a new research note and existing active notes.
    """
    new_direction = classify_claim_direction(new_content)
    contradictions: List[Contradiction] = []

    for note in existing_notes:
        if getattr(note, "status", "active") != "active":
            continue

        note_symbol = getattr(note, "symbol", None)
        if new_symbol and note_symbol and new_symbol.upper() == note_symbol.upper():
            existing_direction = classify_claim_direction(note.content)

            is_opposing = (
                (new_direction == ClaimDirection.BULLISH and existing_direction == ClaimDirection.BEARISH) or
                (new_direction == ClaimDirection.BEARISH and existing_direction == ClaimDirection.BULLISH) or
                (new_direction == ClaimDirection.RISK_ALERT and existing_direction == ClaimDirection.BULLISH and note.confidence > 0.7) or
                (new_direction == ClaimDirection.BULLISH and existing_direction == ClaimDirection.RISK_ALERT and new_confidence > 0.7)
            )

            if is_opposing:
                conf_diff = abs(new_confidence - getattr(note, "confidence", 0.5))
                reason = (
                    f"Directional conflict on {new_symbol}: new claim is {new_direction.value} "
                    f"while active note #{note.id} ({note.created_at.date()}) is {existing_direction.value}"
                )
                contradictions.append(Contradiction(
                    note_id=None,
                    conflicting_note_id=note.id,
                    symbol=new_symbol.upper(),
                    reason=reason,
                    confidence_difference=round(conf_diff, 4),
                ))

    return contradictions
