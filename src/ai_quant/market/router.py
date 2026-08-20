from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .models import AssetPayload, SearchResponse
from .providers import ProviderError
from .service import MarketAssetService

router = APIRouter(
    prefix="/api/market",
    tags=["market"],
)


def market_service(request: Request) -> MarketAssetService:
    if hasattr(request.app.state, "market_service"):
        return request.app.state.market_service
    # Lazy fallback instantiation
    import httpx
    from .providers import (
        CoinGeckoClient,
        FredClient,
        ReferenceFeedClient,
        YahooMarketClient,
    )
    from .sec_edgar import SecEdgarClient

    http = httpx.AsyncClient(timeout=httpx.Timeout(5.0))
    return MarketAssetService(
        yahoo=YahooMarketClient(http),
        sec=SecEdgarClient(http, user_agent="AIQuantPlatform/1.2 research@quantplatform.internal"),
        crypto=CoinGeckoClient(http),
        fred=FredClient(http),
        reference=ReferenceFeedClient(http),
    )


@router.get(
    "/search",
    response_model=SearchResponse,
)
async def search_market(
    q: Annotated[
        str,
        Query(
            min_length=1,
            max_length=64,
        ),
    ],
    service: MarketAssetService = Depends(market_service),
) -> SearchResponse:
    return await service.search(q)


@router.get(
    "/asset/{symbol:path}",
    response_model=AssetPayload,
)
async def get_market_asset(
    symbol: str,
    service: MarketAssetService = Depends(market_service),
) -> AssetPayload:
    try:
        return await service.fetch_market_asset_payload(symbol)
    except ProviderError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
