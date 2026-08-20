"""Compatibility alias for intelligence.fundamentals"""
from .intelligence.fundamentals import *
from .intelligence.fundamentals import (
    SECCompanyFactsClient,
    analyze_fundamental,
)

__all__ = ["SECCompanyFactsClient", "analyze_fundamental"]
