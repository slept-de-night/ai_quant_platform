"""Compatibility alias for core.models"""
from .core.models import *
from .core import models as _mod
__all__ = [k for k in dir(_mod) if not k.startswith('_')]
