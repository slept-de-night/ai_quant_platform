"""Compatibility alias for quant.backtest"""
from .quant.backtest import *
from .quant.backtest import (
    metrics_from_returns,
    run_backtest,
)

__all__ = ["metrics_from_returns", "run_backtest"]
