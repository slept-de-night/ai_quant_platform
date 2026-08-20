from __future__ import annotations

import asyncio
import math
import os
from datetime import date
from typing import Any, Dict, List, Optional
from urllib.parse import quote
import httpx
import pandas as pd

from .cache import AsyncTTLCache


class ProviderError(RuntimeError):
    pass


def raw_value(value: Any) -> Any:
    if isinstance(value, dict):
        if "raw" in value:
            return value["raw"]
        if "fmt" in value:
            return value["fmt"]
    return value


async def get_json_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    attempts: int = 3,
) -> Dict[str, Any]:
    last_error: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            response = await client.get(
                url,
                params=params,
                headers=headers,
            )
            if response.status_code == 429:
                raise ProviderError("rate limited")
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ProviderError("provider did not return an object")
            return payload
        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.HTTPStatusError,
            ProviderError,
        ) as exc:
            last_error = exc
            if attempt + 1 == attempts:
                break
            await asyncio.sleep(0.15 * (2**attempt))
    raise ProviderError(str(last_error))


class YahooMarketClient:
    SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
    CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"

    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self.search_cache = AsyncTTLCache[List[Dict[str, Any]]](
            ttl_seconds=30,
            max_size=1000,
        )
        self.chart_cache = AsyncTTLCache[Dict[str, Any]](
            ttl_seconds=5,
            max_size=1000,
        )

    @staticmethod
    def _headers() -> Dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 QuantWorkstation/1.2",
            "Accept": "application/json",
        }

    async def search(
        self,
        query_text: str,
        *,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        key = query_text.strip().lower()

        async def load() -> List[Dict[str, Any]]:
            try:
                payload = await get_json_with_retry(
                    self.http,
                    self.SEARCH_URL,
                    params={
                        "q": query_text,
                        "quotesCount": limit,
                        "newsCount": 0,
                        "enableFuzzyQuery": "false",
                    },
                    headers=self._headers(),
                )
                quotes = payload.get("quotes", [])
                results = [item for item in quotes if isinstance(item, dict)]
                if results:
                    return results
            except Exception:
                pass

            # Fallback/supplement to local cross-asset candidates
            q_lower = query_text.lower()
            candidates = [
                {"symbol": "GLD", "shortname": "SPDR Gold Shares (Physical Trust)", "quoteType": "ETF", "exchange": "NYSE"},
                {"symbol": "GC=F", "shortname": "Gold Futures (COMEX)", "quoteType": "FUTURE", "exchange": "COMEX"},
                {"symbol": "SLV", "shortname": "iShares Silver Trust", "quoteType": "ETF", "exchange": "NYSE"},
                {"symbol": "SI=F", "shortname": "Silver Futures (COMEX)", "quoteType": "FUTURE", "exchange": "COMEX"},
                {"symbol": "NVDA", "shortname": "NVIDIA Corporation", "quoteType": "EQUITY", "exchange": "NASDAQ"},
                {"symbol": "DRAM", "shortname": "Defiance Pure Play Memory & Semis ETF", "quoteType": "ETF", "exchange": "NYSE"},
                {"symbol": "SPY", "shortname": "SPDR S&P 500 ETF Trust", "quoteType": "ETF", "exchange": "NYSE"},
                {"symbol": "QQQ", "shortname": "Invesco QQQ Trust (Nasdaq-100)", "quoteType": "ETF", "exchange": "NASDAQ"},
                {"symbol": "BTC-USD", "shortname": "Bitcoin USD", "quoteType": "CRYPTOCURRENCY", "exchange": "CCC"},
                {"symbol": "ETH-USD", "shortname": "Ethereum USD", "quoteType": "CRYPTOCURRENCY", "exchange": "CCC"},
                {"symbol": "SOL-USD", "shortname": "Solana USD", "quoteType": "CRYPTOCURRENCY", "exchange": "CCC"},
                {"symbol": "EURUSD=X", "shortname": "EUR/USD Currency Pair", "quoteType": "CURRENCY", "exchange": "CCY"},
                {"symbol": "USDJPY=X", "shortname": "USD/JPY Currency Pair", "quoteType": "CURRENCY", "exchange": "CCY"},
            ]
            return [c for c in candidates if q_lower in c["symbol"].lower() or q_lower in c["shortname"].lower() or (q_lower == "gold" and "gold" in c["shortname"].lower())]

        return await self.search_cache.get_or_set(
            f"{key}:{limit}",
            load,
        )


    async def chart(
        self,
        symbol: str,
        *,
        range_: str = "5d",
        interval: str = "1d",
    ) -> Dict[str, Any]:
        normalized = symbol.upper().strip()
        key = f"{normalized}:{range_}:{interval}"

        async def load() -> Dict[str, Any]:
            encoded = quote(normalized, safe="")
            payload = await get_json_with_retry(
                self.http,
                self.CHART_URL.format(symbol=encoded),
                params={
                    "range": range_,
                    "interval": interval,
                    "includePrePost": "false",
                    "events": "div,splits",
                },
                headers=self._headers(),
            )
            result = payload.get("chart", {}).get("result")
            if not result:
                raise ProviderError(f"No chart data for {normalized}")
            return result[0]

        return await self.chart_cache.get_or_set(
            key,
            load,
        )

    async def price_series(
        self,
        symbol: str,
        *,
        range_: str,
        interval: str,
    ) -> pd.Series:
        try:
            result = await self.chart(
                symbol,
                range_=range_,
                interval=interval,
            )
            timestamps = result.get("timestamp") or []
            indicators = result.get("indicators", {})
            quote_rows = indicators.get("quote") or []
            if not quote_rows:
                return pd.Series(dtype=float)
            closes = quote_rows[0].get("close") or []
            if len(timestamps) != len(closes):
                return pd.Series(dtype=float)
            series = pd.Series(
                closes,
                index=pd.to_datetime(
                    timestamps,
                    unit="s",
                    utc=True,
                ),
                dtype=float,
            )
            return series.dropna()
        except Exception:
            return pd.Series(dtype=float)

    async def quote_summary(
        self,
        symbol: str,
        modules: List[str],
    ) -> Dict[str, Any]:
        encoded = quote(symbol.upper().strip(), safe="")
        try:
            payload = await get_json_with_retry(
                self.http,
                self.SUMMARY_URL.format(symbol=encoded),
                params={
                    "modules": ",".join(modules),
                },
                headers=self._headers(),
            )
            result = payload.get("quoteSummary", {}).get("result")
            if not result:
                return {}
            return result[0]
        except Exception:
            return {}


class CoinGeckoClient:
    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self.api_key = os.getenv("COINGECKO_API_KEY")
        self.cache = AsyncTTLCache[Dict[str, Any]](
            ttl_seconds=60,
            max_size=500,
        )

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 QuantWorkstation/1.2",
        }
        if self.api_key:
            headers["x-cg-demo-api-key"] = self.api_key
        return headers

    async def coin(self, coin_id: str) -> Dict[str, Any]:
        async def load() -> Dict[str, Any]:
            try:
                return await get_json_with_retry(
                    self.http,
                    f"{self.BASE_URL}/coins/{coin_id}",
                    params={
                        "localization": "false",
                        "tickers": "false",
                        "market_data": "true",
                        "community_data": "false",
                        "developer_data": "false",
                        "sparkline": "false",
                    },
                    headers=self._headers(),
                )
            except Exception:
                # Built-in reference fallback for major coins
                defaults = {
                    "bitcoin": {
                        "market_data": {
                            "circulating_supply": 19780000.0,
                            "max_supply": 21000000.0,
                            "ath": {"usd": 108900.0},
                        }
                    },
                    "ethereum": {
                        "market_data": {
                            "circulating_supply": 120200000.0,
                            "max_supply": None,
                            "ath": {"usd": 4890.0},
                        }
                    },
                    "solana": {
                        "market_data": {
                            "circulating_supply": 471500000.0,
                            "max_supply": None,
                            "ath": {"usd": 260.0},
                        }
                    },
                }
                return defaults.get(coin_id, {})

        return await self.cache.get_or_set(
            coin_id,
            load,
        )


class FredClient:
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self.api_key = os.getenv("FRED_API_KEY")
        self.cache = AsyncTTLCache[pd.Series](
            ttl_seconds=3600,
            max_size=100,
        )

    async def series(
        self,
        series_id: str,
        *,
        observation_start: Optional[date] = None,
    ) -> pd.Series:
        if not self.api_key:
            return pd.Series(dtype=float)
        cache_key = f"{series_id}:{observation_start.isoformat() if observation_start else ''}"

        async def load() -> pd.Series:
            params: Dict[str, str] = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
            }
            if observation_start:
                params["observation_start"] = observation_start.isoformat()
            payload = await get_json_with_retry(
                self.http,
                self.BASE_URL,
                params=params,
            )
            observations = payload.get("observations", [])
            dates: List[pd.Timestamp] = []
            values: List[float] = []
            for row in observations:
                value = row.get("value")
                if value in {None, "."}:
                    continue
                try:
                    numeric = float(value)
                except ValueError:
                    continue
                if not math.isfinite(numeric):
                    continue
                dates.append(pd.Timestamp(row["date"], tz="UTC"))
                values.append(numeric)
            return pd.Series(
                values,
                index=pd.DatetimeIndex(dates),
                dtype=float,
            )

        return await self.cache.get_or_set(
            cache_key,
            load,
        )


class ReferenceFeedClient:
    """Adapter around institutional multi-asset / reference data feeds."""

    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self.base_url = (os.getenv("MARKET_REFERENCE_BASE_URL") or "").rstrip("/")
        self.api_key = os.getenv("MARKET_REFERENCE_API_KEY")

    async def _get(self, path: str) -> Dict[str, Any]:
        if not self.base_url:
            return {}
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            return await get_json_with_retry(
                self.http,
                f"{self.base_url}{path}",
                headers=headers,
            )
        except ProviderError:
            return {}

    async def fund(self, symbol: str) -> Dict[str, Any]:
        return await self._get(f"/v1/funds/{quote(symbol, safe='')}")

    async def commodity(self, symbol: str) -> Dict[str, Any]:
        return await self._get(f"/v1/commodities/{quote(symbol, safe='')}")

    async def forex(self, symbol: str) -> Dict[str, Any]:
        return await self._get(f"/v1/forex/{quote(symbol, safe='')}")
