from fastapi.testclient import TestClient
from ai_quant.server import app

client = TestClient(app)


def test_status_endpoint():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "models" in data
    assert "spend_limits" in data
    assert data["live_trading"] == "DISABLED_BY_DESIGN (PAPER ONLY)"


def test_strategies_endpoint():
    response = client.get("/api/strategies")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    names = [s["name"] for s in data]
    assert "trend_momentum" in names


def test_backtest_endpoint():
    payload = {
        "symbol": "SPY",
        "strategy": "trend_momentum",
        "days": 400
    }
    response = client.post("/api/quant/backtest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert "daily" in data
    assert len(data["daily"]) > 0
    assert "sharpe" in data["metrics"]


def test_runtime_plan_endpoint():
    payload = {"symbol": "NVDA"}
    response = client.post("/api/runtime/plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "root_id" in data
    assert len(data["nodes"]) > 0


def test_model_deployments_endpoint():
    response = client.get("/api/models/deployments")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_memory_notes_endpoint():
    response = client.get("/api/memory/notes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_paper_cycle_endpoint():
    response = client.get("/api/paper/cycle?symbol=SPY&strategy=trend_momentum")
    assert response.status_code == 200
    data = response.json()
    assert "signal" in data
    assert "portfolio" in data
    assert "risk_decision" in data
    assert "approved" in data["risk_decision"]


def test_risk_metrics_endpoint():
    response = client.get("/api/risk/metrics?symbol=SPY&days=252")
    assert response.status_code == 200
    data = response.json()
    assert "var_95_usd" in data
    assert "var_99_usd" in data
    assert "cvar_95_usd" in data
    assert "sharpe_ratio" in data
    assert "annualized_volatility" in data


def test_architecture_endpoint():
    response = client.get("/api/architecture")
    assert response.status_code == 200
    data = response.json()
    assert "layers" in data
    assert len(data["layers"]) == 7
    layer_ids = [l["id"] for l in data["layers"]]
    assert "layer_1" in layer_ids
    assert "layer_7" in layer_ids


def test_chat_endpoint():
    payload = {
        "messages": [
            {"role": "user", "content": "Explain NVDA's balance sheet and solvency."}
        ],
        "symbol": "NVDA"
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "model" in data


def test_readiness_endpoint():
    response = client.get("/api/readiness")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "trading_readiness" in data
    assert "reconciliation" in data
    assert "market_data" in data
    assert "blocking_reasons" in data


def test_kill_and_unfreeze_endpoints():
    # Test engage kill switch
    response = client.post("/api/risk/kill", json={"reason": "test freeze", "requested_by": "tester"})
    assert response.status_code == 200
    data = response.json()
    assert data.get("is_frozen") is True

    # Test unfreeze
    unfreeze_res = client.post(
        "/api/risk/unfreeze",
        json={"reason": "test unfreeze", "requested_by": "tester", "override": True},
    )
    assert unfreeze_res.status_code in (200, 409)



