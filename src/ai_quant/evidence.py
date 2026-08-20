"""Compatibility alias for intelligence.evidence"""
from .intelligence.evidence import *
from .intelligence.evidence import (
    PRIMARY_DOMAINS,
    TRUSTED_SECONDARY_DOMAINS,
    UNTRUSTED_DOMAINS,
    domain_of,
    inspect_untrusted_text,
    classify_source,
    verify_evidence,
)

__all__ = [
    "PRIMARY_DOMAINS",
    "TRUSTED_SECONDARY_DOMAINS",
    "UNTRUSTED_DOMAINS",
    "domain_of",
    "inspect_untrusted_text",
    "classify_source",
    "verify_evidence",
]
