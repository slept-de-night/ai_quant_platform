import pytest
from fastapi.testclient import TestClient
from ai_quant.api.server import app

client = TestClient(app)


def test_missing_quote_does_not_fabricate_fake_price():
    """Verify that querying a non-existent or failed quote never produces a fake 150.0 price."""
    # When requesting an unknown symbol quote from API
    response = client.get("/api/market/quote/NONEXISTENT_SYMBOL_XYZ")
    # Even if handled with fallback or error, it must never return a hardcoded 150.0 constant
    if response.status_code == 200:
        data = response.json()
        price = data.get("regular_market_price") or data.get("price")
        assert price is None or price == 0.0 or data.get("status") == "unavailable"
        assert price != 150.0, "API must not fabricate default $150.0 price"
    else:
        assert response.status_code in (404, 500, 502, 503)


def test_missing_fundamentals_does_not_fabricate_fake_company_name():
    """Verify that querying fundamentals for a missing ticker does not fabricate a placeholder company."""
    response = client.get("/api/market/fundamentals/NONEXISTENT_SYMBOL_XYZ")
    if response.status_code == 200:
        data = response.json()
        assert data.get("company_name") != "NONEXISTENT_SYMBOL_XYZ Corporation"
    else:
        assert response.status_code in (404, 500, 502, 503)
