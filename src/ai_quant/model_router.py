"""Compatibility alias for runtime.router"""
from .runtime.router import *
from .runtime.router import (
    RouteRequest,
    ModelDecision,
    ModelRouter,
)

__all__ = ["RouteRequest", "ModelDecision", "ModelRouter"]
