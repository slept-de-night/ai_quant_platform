"""Compatibility alias for intelligence.trends"""
from .intelligence.trends import *
from .intelligence.trends import (
    FREDClient,
    analyze_microtrend,
    analyze_megatrend,
)

__all__ = ["FREDClient", "analyze_microtrend", "analyze_megatrend"]
