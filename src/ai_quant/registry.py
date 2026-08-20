"""Compatibility alias for core.registry"""
from .core.registry import *
from .core import registry as _mod
__all__ = [k for k in dir(_mod) if not k.startswith('_')]
