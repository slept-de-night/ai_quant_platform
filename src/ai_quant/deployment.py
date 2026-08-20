"""Compatibility alias for runtime.deployment"""
from .runtime.deployment import *
from .runtime.deployment import (
    DeploymentStatus,
    DeploymentResolution,
    RoutingOverride,
    ModelControlPlane,
)

__all__ = [
    "DeploymentStatus",
    "DeploymentResolution",
    "RoutingOverride",
    "ModelControlPlane",
]
