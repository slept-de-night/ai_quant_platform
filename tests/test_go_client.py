from ai_quant.go_client import GoEngineClient
from ai_quant.models import OrderIntent, Side


def test_go_client_health():
    client = GoEngineClient()
    # In Docker or local environment
    if client.is_available():
        h = client.health()
        assert h is not None
        assert h["engine"] == "aq-engine-go"
        assert h["status"] == "healthy"


def test_go_client_risk_evaluation():
    client = GoEngineClient()
    if client.is_available():
        order = OrderIntent(
            symbol="SPY",
            strategy_name="trend_momentum",
            side=Side.BUY,
            qty=5,
            reference_price=512.0,
            notional=2560.0,
            client_order_id=f"test-integ-{id(client)}",
            reason="Integration test"
        )
        res = client.check_risk(order)
        assert res is not None
        assert "approved" in res
