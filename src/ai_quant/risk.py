"""Compatibility alias for execution.risk"""
from .execution.risk import *
from .execution.risk import (
    calculate_parametric_var,
    calculate_historical_var,
    calculate_cvar,
    calculate_institutional_risk_profile,
    RiskEngine,
)

__all__ = [
    "calculate_parametric_var",
    "calculate_historical_var",
    "calculate_cvar",
    "calculate_institutional_risk_profile",
    "RiskEngine",
]
