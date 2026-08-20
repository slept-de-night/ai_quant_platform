"""Compatibility alias for data.market_data"""
from .data.market_data import *
from .data import market_data as _mod
__all__ = [k for k in dir(_mod) if not k.startswith('_')]
