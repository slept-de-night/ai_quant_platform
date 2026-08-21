from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote
import httpx
import pandas as pd

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 QuantWorkstation/1.2",
    "Accept": "application/json",
}


def fetch_stock_bars_yahoo(symbol: str, days: int = 365) -> pd.DataFrame:
    """Fetch daily stock bars from Yahoo Finance."""
    range_str = "1y" if days <= 365 else "2y" if days <= 730 else "5y"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol.upper().strip())}"
    params = {"range": range_str, "interval": "1d", "includePrePost": "false"}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=HEADERS, params=params)
            if resp.status_code == 200:
                payload = resp.json()
                results = payload.get("chart", {}).get("result")
                if results:
                    res = results[0]
                    timestamps = res.get("timestamp", [])
                    indicators = res.get("indicators", {})
                    quote_data = indicators.get("quote", [{}])[0]
                    if timestamps and quote_data.get("close"):
                        df = pd.DataFrame(
                            {
                                "date": pd.to_datetime(timestamps, unit="s", utc=True),
                                "open": quote_data.get("open", []),
                                "high": quote_data.get("high", []),
                                "low": quote_data.get("low", []),
                                "close": quote_data.get("close", []),
                                "volume": quote_data.get("volume", []),
                            }
                        )
                        df = df.dropna(subset=["close"]).set_index("date")
                        df["returns"] = df["close"].pct_change().fillna(0.0)
                        return df
    except Exception as exc:
        logger.warning(f"Failed to fetch Yahoo bars for {symbol}: {exc}")

    from .market_data import synthetic_bars
    return synthetic_bars(symbol, days)


def fetch_stock_chart_data(
    symbol: str,
    range_str: str = "1y",
    interval: str = "1d",
) -> Dict[str, Any]:
    """Fetch raw chart JSON from Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol.upper().strip())}"
    params = {"range": range_str, "interval": interval, "includePrePost": "false"}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=HEADERS, params=params)
            if resp.status_code == 200:
                return resp.json()
    except Exception as exc:
        logger.warning(f"Failed to fetch Yahoo chart data for {symbol}: {exc}")

    return {"chart": {"result": None, "error": {"description": "Unavailable"}}}


def fetch_real_stock_quote(symbol: str) -> Dict[str, Any]:
    """Fetch real-time stock quote from Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol.upper().strip())}"
    params = {"range": "1d", "interval": "1m", "includePrePost": "false"}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=HEADERS, params=params)
            if resp.status_code == 200:
                payload = resp.json()
                results = payload.get("chart", {}).get("result")
                if results:
                    meta = results[0].get("meta", {})
                    return {
                        "symbol": symbol.upper(),
                        "price": meta.get("regularMarketPrice", 0.0),
                        "previous_close": meta.get("previousClose", 0.0),
                        "currency": meta.get("currency", "USD"),
                        "exchange": meta.get("exchangeName", ""),
                        "instrument_type": meta.get("instrumentType", "EQUITY"),
                    }
    except Exception as exc:
        logger.warning(f"Failed to fetch Yahoo quote for {symbol}: {exc}")

    return {
        "symbol": symbol.upper(),
        "price": None,
        "previous_close": None,
        "currency": "USD",
        "exchange": "UNKNOWN",
        "instrument_type": "EQUITY",
        "status": "unavailable",
    }


def fetch_real_stock_news(symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch latest news for a symbol from Yahoo Finance search."""
    url = "https://query1.finance.yahoo.com/v1/finance/search"
    params = {"q": symbol, "quotesCount": 1, "newsCount": limit}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=HEADERS, params=params)
            if resp.status_code == 200:
                payload = resp.json()
                news = payload.get("news", [])
                return [
                    {
                        "uuid": n.get("uuid", ""),
                        "title": n.get("title", ""),
                        "publisher": n.get("publisher", ""),
                        "link": n.get("link", ""),
                        "providerPublishTime": n.get("providerPublishTime", 0),
                        "type": n.get("type", "STORY"),
                    }
                    for n in news
                ]
    except Exception as exc:
        logger.warning(f"Failed to fetch Yahoo news for {symbol}: {exc}")

    return []


def fetch_real_stock_fundamentals(symbol: str) -> Dict[str, Any]:
    """Fetch fundamentals / summary details from Yahoo Finance."""
    modules = ["summaryDetail", "financialData", "defaultKeyStatistics", "assetProfile"]
    url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{quote(symbol.upper().strip())}"
    params = {"modules": ",".join(modules)}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=HEADERS, params=params)
            if resp.status_code == 200:
                payload = resp.json()
                results = payload.get("quoteSummary", {}).get("result")
                if results:
                    return results[0]
    except Exception as exc:
        logger.warning(f"Failed to fetch fundamentals for {symbol}: {exc}")

    return {}


def fetch_watchlist_summary(symbols: List[str]) -> List[Dict[str, Any]]:
    """Fetch quote summaries for a list of watchlist symbols."""
    out = []
    for sym in symbols:
        out.append(fetch_real_stock_quote(sym))
    return out


def search_market_assets(query: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Search market assets via Yahoo search API."""
    url = "https://query1.finance.yahoo.com/v1/finance/search"
    params = {"q": query, "quotesCount": limit, "newsCount": 0}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=HEADERS, params=params)
            if resp.status_code == 200:
                payload = resp.json()
                return payload.get("quotes", [])
    except Exception as exc:
        logger.warning(f"Failed to search market assets for {query}: {exc}")

    return []
