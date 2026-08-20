"""Compatibility alias for core.config"""
from .core.config import *
from .core import config as _mod
__all__ = [k for k in dir(_mod) if not k.startswith('_')]
