from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from typing import Any

from ..core.models import OrderIntent, PortfolioState, Side
from ..core.registry import Registry


class AlpacaPaperBroker:
    """Alpaca Paper Trading Broker API adapter."""

    def __init__(self, api_key: str, secret_key: str, registry: Registry):
        if not api_key or not secret_key:
            raise ValueError("Alpaca credentials required")
        from alpaca.trading.client import TradingClient

        self.client = TradingClient(api_key, secret_key, paper=True)
        self.registry = registry

    def portfolio_state(self, symbol: str) -> PortfolioState:
        account = self.client.get_account()
        positions = self.client.get_all_positions()
        equity = float(account.equity)
        cash = float(account.cash)
        gross = 0.0
        sym_exp = 0.0
        sym_qty = 0.0

        for p in positions:
            mv = abs(float(p.market_value))
            gross += mv
            if p.symbol == symbol:
                sym_exp = mv
                sym_qty = float(p.qty)

        self.registry.observe_equity(equity)
        peak = self.registry.peak_equity(equity)
        start = self.registry.daily_start_equity(equity)

        utc_day = datetime.now(timezone.utc).date().isoformat()
        with sqlite3.connect(self.registry.path) as c:
            orders_today = c.execute(
                "SELECT COUNT(*) FROM order_log WHERE substr(ts,1,10)=?", (utc_day,)
            ).fetchone()[0]

        return PortfolioState(
            equity=equity,
            cash=cash,
            gross_exposure=gross,
            daily_pnl=equity - start,
            peak_equity=peak,
            current_symbol_exposure=sym_exp,
            current_symbol_qty=sym_qty,
            orders_today=orders_today,
        )

    def submit(self, o: OrderIntent) -> Any:
        if not self.registry.reserve_order(o):
            raise RuntimeError(f"Duplicate client order id blocked locally: {o.client_order_id}")
        try:
            from alpaca.trading.enums import OrderSide, TimeInForce
            from alpaca.trading.requests import MarketOrderRequest

            side = OrderSide.BUY if o.side == Side.BUY else OrderSide.SELL
            req = MarketOrderRequest(
                symbol=o.symbol,
                qty=o.qty,
                side=side,
                time_in_force=TimeInForce.DAY,
                client_order_id=o.client_order_id,
            )
            result = self.client.submit_order(order_data=req)
            self.registry.mark_order(o.client_order_id, "submitted", str(result.id))
            return result
        except Exception:
            self.registry.mark_order(o.client_order_id, "submit_failed")
            raise
