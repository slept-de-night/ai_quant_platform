"""Compatibility alias for data.yahoo"""
from .data.yahoo import *
from .data.yahoo import (
    fetch_stock_bars_yahoo,
    fetch_real_stock_quote,
    fetch_real_stock_news,
    fetch_real_stock_fundamentals,
    fetch_stock_chart_data,
    fetch_watchlist_summary,
)

__all__ = [
    "fetch_stock_bars_yahoo",
    "fetch_real_stock_quote",
    "fetch_real_stock_news",
    "fetch_real_stock_fundamentals",
    "fetch_stock_chart_data",
    "fetch_watchlist_summary",
]
