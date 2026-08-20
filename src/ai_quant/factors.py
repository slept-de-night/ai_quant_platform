"""Compatibility alias for quant.factors"""
from .quant.factors import *
from .quant.factors import (
    ALLOWED_TRANSFORMS,
    validate_spec,
    compile_score,
    seed_strategies,
)

__all__ = ["ALLOWED_TRANSFORMS", "validate_spec", "compile_score", "seed_strategies"]
