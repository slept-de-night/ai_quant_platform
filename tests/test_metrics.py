from fastapi.testclient import TestClient
from ai_quant.api.server import app
from ai_quant.core.metrics import metrics


def test_platform_metrics_tracking():
    metrics.inc_research_runs(2)
    metrics.record_router_latency(45.5)
    metrics.inc_backtest_runs(1)
    metrics.inc_memory_contradictions(1)

    snap = metrics.snapshot()
    assert snap["research_runs_total"] >= 2
    assert snap["model_router_calls"] >= 1
    assert snap["model_router_avg_latency_ms"] > 0
    assert snap["backtest_runs_total"] >= 1
    assert snap["memory_contradictions_total"] >= 1


def test_api_metrics_endpoint():
    client = TestClient(app)
    res = client.get("/api/v1/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "uptime_seconds" in data
    assert "research_runs_total" in data
    assert "memory_notes_total" in data
