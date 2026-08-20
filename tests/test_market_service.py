import pytest
from fastapi.testclient import TestClient

from ai_quant.api.server import app
from ai_quant.market.classify import classify_asset
from ai_quant.market.models import AssetType, InstrumentType


def test_asset_classification():
    assert classify_asset("GLD", "ETF") == (AssetType.COMMODITY, InstrumentType.TRUST)
    assert classify_asset("SLV", "ETF") == (AssetType.COMMODITY, InstrumentType.TRUST)
    assert classify_asset("GC=F", "FUTURE") == (AssetType.COMMODITY, InstrumentType.FUTURE)
    assert classify_asset("BTC-USD", "CRYPTOCURRENCY") == (AssetType.CRYPTO, InstrumentType.CRYPTO)
    assert classify_asset("EURUSD=X", "CURRENCY") == (AssetType.FOREX, InstrumentType.FX_SPOT)
    assert classify_asset("DRAM", "ETF") == (AssetType.ETF, InstrumentType.ETF)
    assert classify_asset("SPY", "ETF") == (AssetType.ETF, InstrumentType.ETF)
    assert classify_asset("NVDA", "EQUITY") == (AssetType.EQUITY, InstrumentType.STOCK)


def test_market_search_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/market/search?q=gold")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) > 0
        symbols = [r["symbol"] for r in data["results"]]
        assert any("G" in s for s in symbols)


def test_market_asset_equity_payload():
    with TestClient(app) as client:
        response = client.get("/api/market/asset/NVDA")
        assert response.status_code == 200
        data = response.json()
        assert data["asset_type"] == "EQUITY"
        assert data["symbol"] == "NVDA"
        assert "profile" in data
        assert "financials" in data["profile"]
        assert "forensics" in data["profile"]
        assert data["profile"]["forensics"]["altman_z"]["score"] is not None
        assert data["profile"]["forensics"]["piotroski_f"]["score"] is not None


def test_market_asset_etf_payload():
    with TestClient(app) as client:
        response = client.get("/api/market/asset/DRAM")
        assert response.status_code == 200
        data = response.json()
        assert data["asset_type"] == "ETF"
        assert data["symbol"] == "DRAM"
        assert "top_holdings" in data["profile"]
        assert len(data["profile"]["top_holdings"]) > 0
        assert data["profile"]["top_holdings"][0]["name"] == "Micron Technology Inc."


def test_market_asset_commodity_payload():
    with TestClient(app) as client:
        response = client.get("/api/market/asset/GLD")
        assert response.status_code == 200
        data = response.json()
        assert data["asset_type"] == "COMMODITY"
        assert data["symbol"] == "GLD"
        assert data["instrument_type"] == "TRUST"
        assert data["profile"]["commodity_name"] == "Gold"
        assert "vault_custodian" in data["profile"]


def test_market_asset_crypto_payload():
    with TestClient(app) as client:
        response = client.get("/api/market/asset/BTC-USD")
        assert response.status_code == 200
        data = response.json()
        assert data["asset_type"] == "CRYPTO"
        assert data["symbol"] == "BTC-USD"
        assert data["profile"]["circulating_supply"] is not None
        assert data["profile"]["ath_drawdown_pct"] is not None
        assert data["profile"]["trades_24_7"] is True


def test_market_asset_forex_payload():
    with TestClient(app) as client:
        response = client.get("/api/market/asset/EURUSD=X")
        assert response.status_code == 200
        data = response.json()
        assert data["asset_type"] == "FOREX"
        assert data["profile"]["base_currency"] == "EUR"
        assert data["profile"]["quote_currency"] == "USD"
        assert data["profile"]["interest_rate_differential_pct"] is not None
