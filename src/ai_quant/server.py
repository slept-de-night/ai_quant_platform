"""Compatibility alias for api.server"""
from .api.server import *
from .api.server import (
    app,
    bars_for,
    registry,
    go_client,
    seed_db,
)

__all__ = ["app", "bars_for", "registry", "go_client", "seed_db"]
