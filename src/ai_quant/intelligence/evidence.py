from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from .models import (
    ClaimAssessment,
    EvidenceItem,
    EvidenceReport,
    EvidenceVerdict,
    SourceTier,
)

PRIMARY_DOMAINS: Set[str] = {
    "sec.gov",
    "data.sec.gov",
    "www.sec.gov",
    "federalreserve.gov",
    "www.federalreserve.gov",
    "treasury.gov",
    "home.treasury.gov",
    "bls.gov",
    "www.bls.gov",
    "bea.gov",
    "www.bea.gov",
    "census.gov",
    "www.census.gov",
    "fdic.gov",
    "www.fdic.gov",
    "finra.org",
    "www.finra.org",
    "investor.gov",
    "www.investor.gov",
}

TRUSTED_SECONDARY_DOMAINS: Set[str] = {
    "reuters.com",
    "www.reuters.com",
    "apnews.com",
    "www.apnews.com",
    "bloomberg.com",
    "www.bloomberg.com",
    "ft.com",
    "www.ft.com",
    "wsj.com",
    "www.wsj.com",
    "cnbc.com",
    "www.cnbc.com",
}

UNTRUSTED_DOMAINS: Set[str] = {
    "reddit.com",
    "www.reddit.com",
    "x.com",
    "twitter.com",
    "stocktwits.com",
    "www.stocktwits.com",
    "quora.com",
    "www.quora.com",
}

INJECTION_PATTERNS: List[str] = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(the\s+)?system\s+prompt",
    r"system\s+message",
    r"developer\s+message",
    r"you\s+are\s+chatgpt",
    r"assistant\s*:",
    r"do\s+not\s+follow\s+previous",
]

ZERO_WIDTH: Set[str] = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"}
BIDI_CONTROLS: Set[str] = {
    chr(x) for x in [0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069]
}


def domain_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _domain_matches(domain: str, candidates: Set[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in candidates)


def inspect_untrusted_text(text: str) -> Tuple[str, List[str]]:
    """Scan and sanitize untrusted news or web text for hidden control chars or prompt injection."""
    reasons: List[str] = []
    if any(ch in text for ch in ZERO_WIDTH):
        reasons.append("zero-width characters detected")
    if any(ch in text for ch in BIDI_CONTROLS):
        reasons.append("bidirectional control characters detected")
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            reasons.append("prompt-injection-like instruction detected")
            break
    control_count = sum(1 for ch in text if unicodedata.category(ch) in {"Cc", "Cf"} and ch not in "\n\r\t")
    if control_count > 0:
        reasons.append(f"{control_count} hidden/control characters detected")

    cleaned = unicodedata.normalize("NFKC", text)
    cleaned = "".join(ch for ch in cleaned if ch not in ZERO_WIDTH and ch not in BIDI_CONTROLS)
    return cleaned, reasons


def classify_source(
    url: str,
    text: str = "",
    extra_primary: Optional[Set[str]] = None,
    extra_trusted: Optional[Set[str]] = None,
) -> Tuple[SourceTier, List[str]]:
    """Classify the trust tier of an external evidence source URL."""
    domain = domain_of(url)
    _, suspicious = inspect_untrusted_text(text)
    if suspicious:
        return SourceTier.SUSPICIOUS, suspicious
    if _domain_matches(domain, PRIMARY_DOMAINS | (extra_primary or set())):
        return SourceTier.PRIMARY, []
    if _domain_matches(domain, TRUSTED_SECONDARY_DOMAINS | (extra_trusted or set())):
        return SourceTier.TRUSTED_SECONDARY, []
    if _domain_matches(domain, UNTRUSTED_DOMAINS):
        return SourceTier.UNTRUSTED, ["user-generated/social source is not admissible for material facts"]
    return SourceTier.SECONDARY, []


def _claim_key(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).lower()
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^\w\s%.$+-]", "", t)
    return t.strip()[:700]


def verify_evidence(items: List[Any]) -> EvidenceReport:
    """Evaluate multi-source corroboration and compute overall evidence trust score."""
    groups: Dict[str, List[EvidenceItem]] = defaultdict(list)
    rejected = 0

    normalized_items: List[EvidenceItem] = []
    for raw in items:
        if isinstance(raw, EvidenceItem):
            normalized_items.append(raw)
        elif isinstance(raw, dict):
            url = raw.get("url") or raw.get("link") or ""
            title = raw.get("title") or "Report"
            claim = raw.get("claim") or title
            raw_tier = raw.get("tier", SourceTier.TRUSTED_SECONDARY)
            tier = raw_tier if isinstance(raw_tier, SourceTier) else SourceTier.TRUSTED_SECONDARY
            normalized_items.append(
                EvidenceItem(
                    claim=claim,
                    url=url,
                    title=title,
                    source_domain=raw.get("source_domain") or domain_of(url),
                    tier=tier,
                    suspicious_text=bool(raw.get("suspicious_text", False)),
                    suspicious_reasons=raw.get("suspicious_reasons", []),
                )
            )

    for item in normalized_items:
        if item.tier in {SourceTier.SUSPICIOUS, SourceTier.UNTRUSTED} or item.suspicious_text:
            rejected += 1
            continue
        groups[_claim_key(item.claim)].append(item)


    assessments: List[ClaimAssessment] = []
    all_domains: Set[str] = set()

    for grouped in groups.values():
        claim = grouped[0].claim
        by_domain: Dict[str, EvidenceItem] = {}
        for item in grouped:
            domain = item.source_domain or domain_of(item.url)
            all_domains.add(domain)
            prev = by_domain.get(domain)
            if prev is None or item.tier == SourceTier.PRIMARY:
                by_domain[domain] = item

        independent = list(by_domain.values())
        primary = sum(i.tier == SourceTier.PRIMARY for i in independent)
        trusted = sum(i.tier == SourceTier.TRUSTED_SECONDARY for i in independent)
        n = len(independent)
        notes: List[str] = []

        if primary >= 1:
            verdict = EvidenceVerdict.VERIFIED
            confidence = min(0.98, 0.88 + 0.03 * min(n - 1, 3))
            notes.append("supported by a primary/official source")
        elif trusted >= 2:
            verdict = EvidenceVerdict.VERIFIED
            confidence = min(0.90, 0.76 + 0.04 * min(trusted - 2, 3))
            notes.append("corroborated by multiple independent trusted secondary sources")
        elif trusted == 1 and n >= 2:
            verdict = EvidenceVerdict.PARTIAL
            confidence = 0.62
            notes.append("one trusted source plus additional independent corroboration")
        elif n >= 2:
            verdict = EvidenceVerdict.PARTIAL
            confidence = 0.52
            notes.append("multiple sources found, but none are in the trusted/primary tier")
        else:
            verdict = EvidenceVerdict.UNVERIFIED
            confidence = 0.28
            notes.append("single-source claim; not enough independent corroboration")

        assessments.append(
            ClaimAssessment(
                claim=claim,
                verdict=verdict,
                confidence=confidence,
                independent_sources=n,
                primary_sources=primary,
                trusted_secondary_sources=trusted,
                sources=independent,
                notes=notes,
            )
        )

    if not assessments:
        return EvidenceReport(
            claims=[],
            overall_trust=0.0,
            verified_claim_ratio=0.0,
            disputed_claims=0,
            rejected_sources=rejected,
            source_domains=sorted(d for d in all_domains if d),
        )

    weights = {
        EvidenceVerdict.VERIFIED: 1.0,
        EvidenceVerdict.PARTIAL: 0.6,
        EvidenceVerdict.UNVERIFIED: 0.2,
        EvidenceVerdict.DISPUTED: 0.0,
        EvidenceVerdict.REJECTED: 0.0,
    }
    overall = sum(weights[a.verdict] * a.confidence for a in assessments) / len(assessments)
    verified = sum(a.verdict == EvidenceVerdict.VERIFIED for a in assessments) / len(assessments)
    disputed = sum(a.verdict == EvidenceVerdict.DISPUTED for a in assessments)

    return EvidenceReport(
        claims=assessments,
        overall_trust=max(0.0, min(1.0, overall)),
        verified_claim_ratio=verified,
        disputed_claims=disputed,
        rejected_sources=rejected,
        source_domains=sorted(d for d in all_domains if d),
    )
