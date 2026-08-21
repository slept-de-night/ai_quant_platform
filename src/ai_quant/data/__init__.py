"""Data access and quantitative feature computation layer."""
from .market_data import (
    synthetic_bars,
    alpaca_daily_bars,
    get_market_bars,
    validate_bars,
)
from .features import (
    FEATURE_COLUMNS,
    feature_frame,
)
from .regime import (
    regime_series,
    latest_regime,
)
from .indicators import (
    compute_technical_indicators,
)
from .yahoo import (
    fetch_stock_bars_yahoo,
    fetch_real_stock_quote,
    fetch_real_stock_news,
    fetch_real_stock_fundamentals,
    fetch_stock_chart_data,
    fetch_watchlist_summary,
    search_market_assets,
)

__all__ = [
    "synthetic_bars",
    "alpaca_daily_bars",
    "get_market_bars",
    "validate_bars",
    "FEATURE_COLUMNS",
    "feature_frame",
    "regime_series",
    "latest_regime",
    "compute_technical_indicators",
    "fetch_stock_bars_yahoo",
    "fetch_real_stock_quote",
    "fetch_real_stock_news",
    "fetch_real_stock_fundamentals",
    "fetch_stock_chart_data",
    "fetch_watchlist_summary",
    "search_market_assets",
]
